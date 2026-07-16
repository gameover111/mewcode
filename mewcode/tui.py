from __future__ import annotations

from collections.abc import Callable

from mewcode.conversation import Conversation
from mewcode.providers.base import (
    ChatProvider,
    ChatRequest,
    ProviderConfig,
    ProviderError,
)


InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]


def run_chat_loop(
    config: ProviderConfig,
    provider: ChatProvider,
    input_func: InputFunc = input,
    output_func: OutputFunc = print,
) -> int:
    conversation = Conversation()
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
        request = ChatRequest(messages=conversation.snapshot(), config=config)
        assistant_parts: list[str] = []

        output_func("MewCode> ")
        try:
            for event in provider.stream_chat(request):
                if event.type == "text":
                    assistant_parts.append(event.content)
                    output_func(event.content)
                elif event.type == "thinking" and event.content:
                    output_func(f"[思考] {event.content}")
                elif event.type == "error":
                    output_func(f"错误：{event.content}")
                elif event.type == "done":
                    break
        except ProviderError as exc:
            output_func(f"错误：{exc}")
            continue

        assistant_text = "".join(assistant_parts)
        if assistant_text:
            conversation.add_assistant_message(assistant_text)
