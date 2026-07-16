from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal, Protocol


ProtocolName = Literal["anthropic", "openai"]
MessageRole = Literal["user", "assistant"]
EventType = Literal["text", "thinking", "error", "done"]


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    protocol: ProtocolName
    model: str
    base_url: str
    api_key: str
    thinking: bool = False


@dataclass(frozen=True)
class ChatMessage:
    role: MessageRole
    content: str


@dataclass(frozen=True)
class ChatRequest:
    messages: list[ChatMessage]
    config: ProviderConfig


@dataclass(frozen=True)
class ProviderEvent:
    type: EventType
    content: str = ""


class ProviderError(Exception):
    """面向用户的 Provider 错误。"""


class ChatProvider(Protocol):
    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]:
        ...
