from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Literal, Protocol


ProtocolName = Literal["anthropic", "openai"]
MessageRole = Literal["system", "user", "assistant", "tool"]
EventType = Literal["text", "thinking", "tool_call", "error", "done"]


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    protocol: ProtocolName
    model: str
    base_url: str
    api_key: str
    thinking: bool = False
    context_window: int = 0  # 0 表示未配置，走协议默认值（F30/F31）


@dataclass(frozen=True)
class ChatMessage:
    role: MessageRole
    content: str
    tool_call_id: str | None = None
    tool_calls: list["ToolCall"] | None = None


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments_json: str


# 新增：系统提示分层
@dataclass
class SystemPrompt:
    stable: str = ""       # 可缓存：装配好的稳定系统模块
    environment: str = ""  # 不缓存：环境信息段


# 扩展：用量增加缓存字段
@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write: int = 0   # Anthropic: cache_creation_input_tokens; OpenAI: 0
    cache_read: int = 0    # Anthropic: cache_read_input_tokens; OpenAI: cached_tokens


@dataclass
class ChatRequest:
    messages: list[ChatMessage]
    config: ProviderConfig
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | None = "auto"
    system: SystemPrompt | None = None     # 新增：分层系统提示
    reminder: str = ""                      # 新增：本轮 system-reminder 内容


@dataclass(frozen=True)
class ProviderEvent:
    type: EventType
    content: str = ""
    tool_call: ToolCall | None = None
    usage: Usage | None = None              # 新增：携带缓存用量


class ProviderError(Exception):
    """面向用户的 Provider 错误。"""


class ChatProvider(Protocol):
    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]:
        ...
