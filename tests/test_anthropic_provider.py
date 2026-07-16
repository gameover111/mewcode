from __future__ import annotations

import json

import httpx
import pytest

from mewcode.providers.anthropic import ClaudeProvider
from mewcode.providers.base import ChatMessage, ChatRequest, ProviderConfig, ProviderError


def make_request(thinking: bool = False) -> ChatRequest:
    return ChatRequest(
        config=ProviderConfig(
            name="claude",
            protocol="anthropic",
            model="claude-test",
            base_url="https://api.example.com/v1/messages",
            api_key="test-key",
            thinking=thinking,
        ),
        messages=[ChatMessage(role="user", content="你好")],
    )


def test_claude_provider_sends_expected_request_and_streams_text():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["json"] = json.loads(request.content.decode("utf-8"))
        content = "\n".join(
            [
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"你"}}',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"好"}}',
                'data: {"type":"message_stop"}',
            ]
        )
        return httpx.Response(200, content=content)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ClaudeProvider(client=client)

    events = list(provider.stream_chat(make_request()))

    assert captured["url"] == "https://api.example.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"]["model"] == "claude-test"
    assert captured["json"]["stream"] is True
    assert captured["json"]["messages"] == [{"role": "user", "content": "你好"}]
    assert [event.content for event in events if event.type == "text"] == ["你", "好"]
    assert events[-1].type == "done"


def test_claude_provider_adds_thinking_config():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content.decode("utf-8"))
        content = "\n".join(
            [
                'data: {"type":"content_block_delta","delta":{"type":"thinking_delta","thinking":"思考"}}',
                'data: {"type":"message_stop"}',
            ]
        )
        return httpx.Response(200, content=content)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ClaudeProvider(client=client)

    events = list(provider.stream_chat(make_request(thinking=True)))

    assert captured["json"]["thinking"]["type"] == "enabled"
    assert captured["json"]["thinking"]["budget_tokens"] > 0
    assert [event.content for event in events if event.type == "thinking"] == ["思考"]


def test_claude_provider_turns_http_error_into_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, content="bad key")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ClaudeProvider(client=client)

    with pytest.raises(ProviderError, match="Claude API 请求失败"):
        list(provider.stream_chat(make_request()))
