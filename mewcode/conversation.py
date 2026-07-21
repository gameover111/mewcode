from __future__ import annotations

from dataclasses import dataclass, field

from mewcode.providers.base import ChatMessage, ToolCall


@dataclass
class Conversation:
    messages: list[ChatMessage] = field(default_factory=list)

    def add_user_message(self, content: str) -> None:
        self.messages.append(ChatMessage(role="user", content=content))

    def add_assistant_message(
        self, content: str, tool_calls: list[ToolCall] | None = None
    ) -> None:
        self.messages.append(
            ChatMessage(role="assistant", content=content, tool_calls=tool_calls)
        )

    def add_assistant_tool_call(self, tool_call: ToolCall) -> None:
        self.messages.append(
            ChatMessage(role="assistant", content="", tool_calls=[tool_call])
        )

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self.messages.append(
            ChatMessage(role="tool", content=content, tool_call_id=tool_call_id)
        )

    def snapshot(self) -> list[ChatMessage]:
        return list(self.messages)

    def replace_history(self, new_messages: list[ChatMessage]) -> None:
        """深拷贝替换整个对话历史（F15）。"""
        import copy
        self.messages = copy.deepcopy(new_messages)
