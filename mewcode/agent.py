# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Literal

from mewcode.conversation import Conversation
from mewcode.providers.base import (
    ChatProvider,
    ChatRequest,
    ChatMessage,
    ProviderConfig,
    ProviderError,
    ProviderEvent,
    ToolCall,
)
from mewcode.tools.base import ToolContext, ToolResult, run_tool
from mewcode.tools.registry import ToolRegistry
from mewcode.prompts import (
    build_system_prompt,
    gather_environment,
    plan_reminder,
    should_inject_plan_reminder,
    PLAN_REMINDER_INTERVAL,
)
from mewcode.providers.base import SystemPrompt

@dataclass(frozen=True)
class AgentEvent:
    type: AgentEventType
    content: str = ""
    round_index: int | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None


@dataclass(frozen=True)
class AgentOptions:
    max_rounds: int = 8
    plan_only: bool = False
    overall_timeout_seconds: float | None = None
    per_round_timeout_seconds: float | None = None


@dataclass
class AgentControl:
    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True


@dataclass
class AgentRunState:
    round_index: int = 0
    terminate_reason: str | None = None
    started_at: float = field(default_factory=time.monotonic)


@dataclass
class ToolExecutionHooks:
    before_tool: Callable[[ToolCall], ToolResult | None] | None = None
    after_tool: Callable[[ToolCall, ToolResult], None] | None = None


ToolKind = Literal["read", "write"]

_READ_TOOLS = {"read_file", "find_files", "search_code"}


def tool_kind(tool_name: str) -> ToolKind:
    if tool_name in _READ_TOOLS:
        return "read"
    return "write"

def _filter_read_tools(registry):
    _READ_TOOLS = {"read_file", "find_files", "search_code"}
    return [t for t in registry.to_openai_tools() if t["function"]["name"] in _READ_TOOLS]


def execute_tool_calls(
    tool_calls: list[ToolCall],
    registry: ToolRegistry,
    context: ToolContext,
    plan_only: bool = False,
    hooks: ToolExecutionHooks | None = None,
) -> list[tuple[ToolCall, ToolResult]]:
    if not tool_calls:
        return []

    read_calls = [(i, tc) for i, tc in enumerate(tool_calls) if tool_kind(tc.name) == "read"]
    write_calls = [(i, tc) for i, tc in enumerate(tool_calls) if tool_kind(tc.name) == "write"]

    results: dict[int, ToolResult] = {}

    if read_calls:
        with ThreadPoolExecutor(max_workers=len(read_calls)) as pool:
            def _do_read(idx_tc):
                orig_idx, tc = idx_tc
                return orig_idx, tc, _exec_one(tc, registry, context, plan_only, hooks)
            futures = [pool.submit(_do_read, item) for item in read_calls]
            for fut in as_completed(futures):
                orig_idx, tc, tr = fut.result()
                results[orig_idx] = tr

    for orig_idx, tc in write_calls:
        tr = _exec_one(tc, registry, context, plan_only, hooks)
        results[orig_idx] = tr

    return [(tc, results[i]) for i, tc in enumerate(tool_calls)]


def _exec_one(
    tc: ToolCall,
    registry: ToolRegistry,
    context: ToolContext,
    plan_only: bool,
    hooks: ToolExecutionHooks | None,
) -> ToolResult:
    if hooks and hooks.before_tool:
        hook_result = hooks.before_tool(tc)
        if hook_result is not None:
            if hooks.after_tool:
                hooks.after_tool(tc, hook_result)
            return hook_result

    if plan_only and tool_kind(tc.name) == "write":
        result = ToolResult(
            ok=False,
            summary=f"[plan-only] 工具 {tc.name} 已被拦截：当前为 plan-only 模式，不允许执行写操作。请关闭 --plan-only 后再执行。",
            error="plan-only 模式：写类工具不允许执行",
        )
        if hooks and hooks.after_tool:
            hooks.after_tool(tc, result)
        return result

    tool = registry.get(tc.name)
    if tool is None:
        result = ToolResult(ok=False, summary=f"未知工具：{tc.name}", error=f"工具未注册：{tc.name}")
        if hooks and hooks.after_tool:
            hooks.after_tool(tc, result)
        return result

    try:
        arguments = json.loads(tc.arguments_json or "{}")
    except json.JSONDecodeError as exc:
        result = ToolResult(ok=False, summary=f"工具参数不是合法 JSON：{tc.name}", error=str(exc))
        if hooks and hooks.after_tool:
            hooks.after_tool(tc, result)
        return result
    if not isinstance(arguments, dict):
        result = ToolResult(ok=False, summary=f"工具参数必须是 JSON 对象：{tc.name}", error="工具参数必须是 JSON 对象。")
        if hooks and hooks.after_tool:
            hooks.after_tool(tc, result)
        return result

    result = run_tool(tool, arguments, context)
    if hooks and hooks.after_tool:
        hooks.after_tool(tc, result)
    return result


def _tool_result_to_json(result: ToolResult) -> str:
    return json.dumps(
        {"ok": result.ok, "summary": result.summary, "data": result.data, "error": result.error},
        ensure_ascii=False,
    )


def stream_agent_reply(
    conversation: Conversation,
    config: ProviderConfig,
    provider: ChatProvider,
    registry: ToolRegistry,
    context: ToolContext,
    options: AgentOptions | None = None,
    control: AgentControl | None = None,
    hooks: ToolExecutionHooks | None = None,
) -> Iterator[AgentEvent]:
    opts = options or AgentOptions()
    ctrl = control or AgentControl()
    state = AgentRunState()

    # 构建稳定系统提示（跨轮不变，走缓存）
    _stable_prompt = build_system_prompt()
    
    # 采集环境信息（每轮变化，不走缓存）
    _env = gather_environment(version="", model=config.model)
    

    yield AgentEvent(type="user_message", round_index=state.round_index)

    while True:
        if ctrl.cancelled:
            yield AgentEvent(type="cancelled", content="用户取消了操作", round_index=state.round_index)
            yield AgentEvent(type="done", round_index=state.round_index)
            return

        if opts.overall_timeout_seconds is not None:
            elapsed = time.monotonic() - state.started_at
            if elapsed > opts.overall_timeout_seconds:
                yield AgentEvent(type="error", content=f"整体超时：已超过 {opts.overall_timeout_seconds} 秒", round_index=state.round_index)
                yield AgentEvent(type="done", round_index=state.round_index)
                return

        if state.round_index >= opts.max_rounds:
            yield AgentEvent(type="error", content=f"达到最大轮数限制 ({opts.max_rounds})，停止循环", round_index=state.round_index)
            yield AgentEvent(type="done", round_index=state.round_index)
            return

        round_start = time.monotonic()
        state.round_index += 1

        # 计算本轮 reminder
        _reminder = ""
        if opts.plan_only and should_inject_plan_reminder(state.round_index):
            _is_full = (state.round_index == 1 or (state.round_index - 1) % PLAN_REMINDER_INTERVAL == 0)
            _reminder = plan_reminder(full=_is_full)
        
        request = ChatRequest(
            messages=conversation.snapshot(),
            config=config,
            tools=registry.to_openai_tools() if not opts.plan_only else _filter_read_tools(registry),
            tool_choice="auto",
            system=SystemPrompt(stable=_stable_prompt, environment=_env.render()),
            reminder=_reminder,
        )

        round_text_parts: list[str] = []
        round_tool_calls: list[ToolCall] = []

        try:
            for event in provider.stream_chat(request):
                if opts.per_round_timeout_seconds is not None:
                    if time.monotonic() - round_start > opts.per_round_timeout_seconds:
                        yield AgentEvent(type="error", content=f"第 {state.round_index} 轮超时：已超过 {opts.per_round_timeout_seconds} 秒", round_index=state.round_index)
                        break

                if opts.overall_timeout_seconds is not None:
                    if time.monotonic() - state.started_at > opts.overall_timeout_seconds:
                        yield AgentEvent(type="error", content=f"整体超时：已超过 {opts.overall_timeout_seconds} 秒", round_index=state.round_index)
                        break
                if ctrl.cancelled:
                    break

                if event.type == "text":
                    round_text_parts.append(event.content)
                    yield AgentEvent(type="text", content=event.content, round_index=state.round_index)
                elif event.type == "thinking":
                    yield AgentEvent(type="thinking", content=event.content, round_index=state.round_index)
                elif event.type == "tool_call" and event.tool_call:
                    round_tool_calls.append(event.tool_call)
                    yield AgentEvent(type="tool_start", content=f"调用工具：{event.tool_call.name}", round_index=state.round_index, tool_call_id=event.tool_call.id, tool_name=event.tool_call.name)
                elif event.type == "error":
                    yield AgentEvent(type="error", content=event.content, round_index=state.round_index)
                elif event.type == "done":
                    break
        except ProviderError as exc:
            yield AgentEvent(type="error", content=str(exc), round_index=state.round_index)
            yield AgentEvent(type="done", round_index=state.round_index)
            return

        if ctrl.cancelled:
            yield AgentEvent(type="cancelled", content="用户取消了操作", round_index=state.round_index)
            yield AgentEvent(type="done", round_index=state.round_index)
            return

        if not round_tool_calls:
            final_text = "".join(round_text_parts)
            if final_text:
                conversation.add_assistant_message(final_text)
            yield AgentEvent(type="final", content=final_text, round_index=state.round_index)
            yield AgentEvent(type="done", round_index=state.round_index)
            return

        conversation.add_assistant_message(
            "".join(round_text_parts),
            tool_calls=[tc for tc in round_tool_calls],
        )

        tool_results = execute_tool_calls(
            round_tool_calls,
            registry,
            context,
            plan_only=opts.plan_only,
            hooks=hooks,
        )

        for tc, tr in tool_results:
            result_json = _tool_result_to_json(tr)
            conversation.add_tool_result(tc.id, result_json)
            yield AgentEvent(
                type="tool_result", content=tr.summary,
                round_index=state.round_index,
                tool_call_id=tc.id, tool_name=tc.name,
            )