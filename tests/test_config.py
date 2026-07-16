from __future__ import annotations

import pytest

from mewcode.config import load_provider_config
from mewcode.providers.base import ProviderError


def test_load_provider_config_with_all_fields(tmp_path):
    path = tmp_path / "mewcode.yaml"
    path.write_text(
        "\n".join(
            [
                "name: claude",
                "protocol: anthropic",
                "model: claude-test",
                "base_url: https://example.com/messages",
                "api_key: test-key",
                "thinking: true",
            ]
        ),
        encoding="utf-8",
    )

    config = load_provider_config(path)

    assert config.name == "claude"
    assert config.protocol == "anthropic"
    assert config.model == "claude-test"
    assert config.base_url == "https://example.com/messages"
    assert config.api_key == "test-key"
    assert config.thinking is True


def test_load_provider_config_defaults_thinking_to_false(tmp_path):
    path = tmp_path / "mewcode.yaml"
    path.write_text(
        "\n".join(
            [
                "name: openai",
                "protocol: openai",
                "model: gpt-test",
                "base_url: https://example.com/chat/completions",
                "api_key: test-key",
            ]
        ),
        encoding="utf-8",
    )

    config = load_provider_config(path)

    assert config.thinking is False


def test_load_provider_config_requires_fields(tmp_path):
    path = tmp_path / "mewcode.yaml"
    path.write_text("name: only-name\n", encoding="utf-8")

    with pytest.raises(ProviderError, match="缺少必填字段"):
        load_provider_config(path)


def test_load_provider_config_rejects_unknown_protocol(tmp_path):
    path = tmp_path / "mewcode.yaml"
    path.write_text(
        "\n".join(
            [
                "name: bad",
                "protocol: other",
                "model: test",
                "base_url: https://example.com",
                "api_key: test-key",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ProviderError, match="不支持的协议"):
        load_provider_config(path)


def test_load_provider_config_missing_file():
    with pytest.raises(ProviderError, match="配置文件不存在"):
        load_provider_config("missing.yaml")
