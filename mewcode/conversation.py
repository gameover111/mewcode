from __future__ import annotations

from dataclasses import dataclass, field

from mewcode.providers.base import ChatMessage


@dataclass
class Conversation:
    messages: list[ChatMessage] = field(default_factory=list)

    def add_user_message(self, content: str) -> None:
        self.messages.append(ChatMessage(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(ChatMessage(role="assistant", content=content))

    def snapshot(self) -> list[ChatMessage]:
        return list(self.messages)
