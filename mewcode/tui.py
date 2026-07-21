from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from mewcode.agent import (
    AgentControl,
    AgentEvent,
    AgentOptions,
    stream_agent_reply,
)
from mewcode.conversation import Conversation
from mewcode.permissions import (
    PermissionManager,
    PermissionMode,
    PermissionRequest,
    PermissionScope,
    next_permission_mode,
)
from mewcode.providers.base import (
    ChatProvider,
    ProviderConfig,
)
from mewcode.tools.base import ToolContext
from mewcode.tools.registry import ToolRegistry, create_default_registry


InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]


def run_chat_loop(
    config: ProviderConfig,
    provider: ChatProvider,
    input_func: InputFunc = input,
    output_func: OutputFunc = print,
    registry: ToolRegistry | None = None,
    workspace: Path | None = None,
    options: AgentOptions | None = None,
) -> int:
    conversation = Conversation()
    registry = registry or create_default_registry()
    workdir = workspace or Path.cwd()
    opts = options or AgentOptions()
    permission_manager = PermissionManager.from_files(
        workdir,
        callback=_permission_prompt(input_func, output_func),
        mode_override=opts.permission_mode,
    )
    tool_context = ToolContext(workspace=workdir, permission_manager=permission_manager)
    output_func(f"欢迎使用 MewCode，当前配置：{config.name}")
    output_func(f"权限模式：{permission_manager.mode.value}")
    output_func("输入 /exit 或 /quit 退出。")

    while True:
        try:
            user_input = input_func("你? ").strip()
        except (EOFError, KeyboardInterrupt):
            output_func("\n已退出 MewCode。")
            return 0

        if not user_input:
            continue
        if user_input in {"/exit", "/quit"}:
            output_func("已退出 MewCode。")
            return 0
        if user_input == "/mode":
            permission_manager.mode = next_permission_mode(permission_manager.mode)
            opts = _with_permission_mode(opts, permission_manager.mode)
            output_func(f"权限模式：{permission_manager.mode.value}")
            continue
        if user_input == "/plan":
            permission_manager.mode = PermissionMode.PLAN
            opts = _with_permission_mode(opts, permission_manager.mode)
            output_func("已进入 plan 模式。")
            continue
        if user_input == "/do":
            permission_manager.mode = PermissionMode.DEFAULT
            opts = _with_permission_mode(opts, permission_manager.mode)
            user_input = "请根据上文计划开始执行。"

        conversation.add_user_message(user_input)

        control = AgentControl()
        _emit(output_func, "MewCode> ", end="")
        for event in stream_agent_reply(
            conversation, config, provider, registry, tool_context,
            options=opts, control=control,
        ):
            if event.type == "text":
                _emit(output_func, event.content, end="")
            elif event.type == "thinking":
                _emit(output_func, "", end="\n")
                _emit(output_func, f"[思考] {event.content}")
            elif event.type == "tool_start":
                _emit(output_func, "", end="\n")
                _emit(output_func, f"[工具] 调用工具：{event.tool_name}")
            elif event.type == "tool_result":
                _emit(output_func, f"[工具结果] {event.content}")
            elif event.type == "final":
                # final 文本已在 text 事件中流式输出，这里不再重复
                pass
            elif event.type == "error":
                _emit(output_func, "", end="\n")
                _emit(output_func, f"错误：{event.content}")
            elif event.type == "cancelled":
                _emit(output_func, "", end="\n")
                _emit(output_func, f"已取消：{event.content}")
            elif event.type == "done":
                break
        output_func("")


def _emit(output_func: OutputFunc, text: str, end: str = "\n") -> None:
    if output_func is print:
        try:
            print(text, end=end, flush=True)
        except UnicodeEncodeError:
            encoding = sys.stdout.encoding or "utf-8"
            safe_text = text.encode(encoding, errors="replace").decode(encoding)
            print(safe_text, end=end, flush=True)
    else:
        output_func(text)


def _permission_prompt(
    input_func: InputFunc,
    output_func: OutputFunc,
) -> Callable[[PermissionRequest], tuple[bool, PermissionScope]]:
    def ask(request: PermissionRequest) -> tuple[bool, PermissionScope]:
        output_func("")
        output_func(f"[权限] 工具 {request.tool_name} 请求执行：{_permission_target(request)}")
        output_func("[权限] 触发原因：当前权限模式需要你确认该操作。")
        output_func("[权限] 1=允许本次，2=永久允许，3=拒绝本次")
        while True:
            try:
                choice = input_func("权限? ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                output_func("[权限] 已取消，按拒绝本次处理。")
                return False, PermissionScope.ONCE
            if choice in {"1", "y", "yes"}:
                return True, PermissionScope.ONCE
            if choice in {"s", "session"}:
                return True, PermissionScope.SESSION
            if choice in {"2", "p", "permanent"}:
                return True, PermissionScope.PERMANENT
            if choice in {"3", "n", "no", ""}:
                return False, PermissionScope.ONCE
            output_func("请输入 1 / 2 / 3。")

    return ask


def _permission_target(request: PermissionRequest) -> str:
    if request.tool_name == "run_command":
        return str(request.arguments.get("command") or "")
    if request.tool_name in {"read_file", "write_file", "replace_in_file"}:
        return str(request.arguments.get("path") or "")
    if request.tool_name == "find_files":
        return str(request.arguments.get("pattern") or "")
    if request.tool_name == "search_code":
        return str(request.arguments.get("query") or request.arguments.get("pattern") or "")
    return str(request.arguments)


def _with_permission_mode(opts: AgentOptions, mode: PermissionMode) -> AgentOptions:
    return AgentOptions(
        max_rounds=opts.max_rounds,
        plan_only=opts.plan_only,
        permission_mode=mode.value,
        overall_timeout_seconds=opts.overall_timeout_seconds,
        per_round_timeout_seconds=opts.per_round_timeout_seconds,
    )
