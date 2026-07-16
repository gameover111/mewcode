from __future__ import annotations

from mewcode.providers.anthropic import ClaudeProvider
from mewcode.providers.base import ChatProvider, ProviderConfig, ProviderError
from mewcode.providers.openai import OpenAIProvider


def create_provider(config: ProviderConfig) -> ChatProvider:
    if config.protocol == "anthropic":
        return ClaudeProvider()
    if config.protocol == "openai":
        return OpenAIProvider()
    raise ProviderError(f"不支持的协议：{config.protocol}")
