from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Literal, Protocol


ProtocolName = Literal["anthropic", "openai"]
MessageRole = Literal["user", "assistant", "tool"]
EventType = Literal["text", "thinking", "tool_call", "error", "done"]


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
    tool_call_id: str | None = None
    tool_calls: list["ToolCall"] | None = None


@dataclass(frozen=True)
class ChatRequest:
    messages: list[ChatMessage]
    config: ProviderConfig
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | None = "auto"


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments_json: str


@dataclass(frozen=True)
class ProviderEvent:
    type: EventType
    content: str = ""
    tool_call: ToolCall | None = None


class ProviderError(Exception):
    """面向用户的 Provider 错误。"""


class ChatProvider(Protocol):
    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]:
        ...
