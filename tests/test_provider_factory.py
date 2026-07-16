from __future__ import annotations

import pytest

from mewcode.providers.anthropic import ClaudeProvider
from mewcode.providers.base import ProviderConfig, ProviderError
from mewcode.providers.factory import create_provider
from mewcode.providers.openai import OpenAIProvider


def make_config(protocol):
    return ProviderConfig(
        name="test",
        protocol=protocol,
        model="test-model",
        base_url="https://example.com",
        api_key="test-key",
    )


def test_create_anthropic_provider():
    assert isinstance(create_provider(make_config("anthropic")), ClaudeProvider)


def test_create_openai_provider():
    assert isinstance(create_provider(make_config("openai")), OpenAIProvider)


def test_create_provider_rejects_unknown_protocol():
    config = make_config("unknown")

    with pytest.raises(ProviderError, match="不支持的协议"):
        create_provider(config)
