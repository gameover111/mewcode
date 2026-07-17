from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from mewcode.agent import stream_agent_reply
from mewcode.conversation import Conversation
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
) -> int:
    conversation = Conversation()
    registry = registry or create_default_registry()
    tool_context = ToolContext(workspace=(workspace or Path.cwd()))
    output_func(f"欢迎使用 MewCode，当前配置：{config.name}")
    output_func("输入 /exit 或 /quit 退出。")

    while True:
        try:
            user_input = input_func("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            output_func("\n已退出 MewCode。")
            return 0

        if not user_input:
            continue
        if user_input in {"/exit", "/quit"}:
            output_func("已退出 MewCode。")
            return 0

        conversation.add_user_message(user_input)

        _emit(output_func, "MewCode> ", end="")
        for event in stream_agent_reply(
            conversation, config, provider, registry, tool_context
        ):
            if event.type == "text":
                _emit(output_func, event.content, end="")
            elif event.type == "tool_start":
                _emit(output_func, "", end="\n")
                _emit(output_func, f"[工具] {event.content}")
            elif event.type == "tool_result":
                _emit(output_func, f"[工具结果] {event.content}")
            elif event.type == "error":
                _emit(output_func, "", end="\n")
                _emit(output_func, f"错误：{event.content}")
            elif event.type == "done":
                break
        output_func("")


def _emit(output_func: OutputFunc, text: str, end: str = "\n") -> None:
    if output_func is print:
        print(text, end=end, flush=True)
    else:
        output_func(text)
