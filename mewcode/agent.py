from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from mewcode.conversation import Conversation
from mewcode.providers.base import (
    ChatProvider,
    ChatRequest,
    ProviderConfig,
    ProviderError,
    ProviderEvent,
    ToolCall,
)
from mewcode.tools.base import ToolContext, ToolResult, run_tool
from mewcode.tools.registry import ToolRegistry


AgentEventType = Literal["text", "tool_start", "tool_result", "error", "done"]


@dataclass(frozen=True)
class AgentEvent:
    type: AgentEventType
    content: str = ""


def stream_agent_reply(
    conversation: Conversation,
    config: ProviderConfig,
    provider: ChatProvider,
    registry: ToolRegistry,
    context: ToolContext,
):
    assistant_parts: list[str] = []
    tool_call: ToolCall | None = None

    first_request = ChatRequest(
        messages=conversation.snapshot(),
        config=config,
        tools=registry.to_openai_tools(),
        tool_choice="auto",
    )
    try:
        for event in provider.stream_chat(first_request):
            if event.type == "text":
                assistant_parts.append(event.content)
                yield AgentEvent(type="text", content=event.content)
            elif event.type == "tool_call":
                tool_call = event.tool_call
                break
            elif event.type == "error":
                yield AgentEvent(type="error", content=event.content)
            elif event.type == "done":
                break
    except ProviderError as exc:
        yield AgentEvent(type="error", content=str(exc))
        yield AgentEvent(type="done")
        return

    if tool_call is None:
        assistant_text = "".join(assistant_parts)
        if assistant_text:
            conversation.add_assistant_message(assistant_text)
        yield AgentEvent(type="done")
        return

    yield AgentEvent(type="tool_start", content=f"调用工具：{tool_call.name}")
    tool_result = _execute_tool_call(tool_call, registry, context)
    result_json = _tool_result_to_json(tool_result)
    yield AgentEvent(type="tool_result", content=tool_result.summary)

    conversation.add_assistant_tool_call(tool_call)
    conversation.add_tool_result(tool_call.id, result_json)

    final_parts: list[str] = []
    final_request = ChatRequest(
        messages=conversation.snapshot(),
        config=config,
        tools=None,
        tool_choice="none",
    )
    try:
        for event in provider.stream_chat(final_request):
            if event.type == "text":
                final_parts.append(event.content)
                yield AgentEvent(type="text", content=event.content)
            elif event.type == "tool_call":
                yield AgentEvent(type="error", content="本章只支持一次工具调用，已停止继续调用工具。")
                yield AgentEvent(type="done")
                return
            elif event.type == "error":
                yield AgentEvent(type="error", content=event.content)
            elif event.type == "done":
                break
    except ProviderError as exc:
        yield AgentEvent(type="error", content=str(exc))
        yield AgentEvent(type="done")
        return

    final_text = "".join(final_parts)
    if final_text:
        conversation.add_assistant_message(final_text)
    yield AgentEvent(type="done")


def _execute_tool_call(
    tool_call: ToolCall, registry: ToolRegistry, context: ToolContext
) -> ToolResult:
    tool = registry.get(tool_call.name)
    if tool is None:
        return ToolResult(
            ok=False,
            summary=f"未知工具：{tool_call.name}",
            error=f"工具未注册：{tool_call.name}",
        )

    try:
        arguments = json.loads(tool_call.arguments_json or "{}")
    except json.JSONDecodeError as exc:
        return ToolResult(
            ok=False,
            summary=f"工具参数不是合法 JSON：{tool_call.name}",
            error=str(exc),
        )
    if not isinstance(arguments, dict):
        return ToolResult(
            ok=False,
            summary=f"工具参数必须是 JSON 对象：{tool_call.name}",
            error="工具参数必须是 JSON 对象。",
        )
    return run_tool(tool, arguments, context)


def _tool_result_to_json(result: ToolResult) -> str:
    return json.dumps(
        {
            "ok": result.ok,
            "summary": result.summary,
            "data": result.data,
            "error": result.error,
        },
        ensure_ascii=False,
    )
