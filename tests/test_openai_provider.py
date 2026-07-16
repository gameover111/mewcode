from __future__ import annotations

import json

import httpx
import pytest

from mewcode.providers.base import ChatMessage, ChatRequest, ProviderConfig, ProviderError
from mewcode.providers.openai import OpenAIProvider


def make_request() -> ChatRequest:
    return ChatRequest(
        config=ProviderConfig(
            name="openai",
            protocol="openai",
            model="gpt-test",
            base_url="https://api.example.com/v1/chat/completions",
            api_key="test-key",
        ),
        messages=[ChatMessage(role="user", content="你好")],
    )


def test_openai_provider_sends_expected_request_and_streams_text():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["json"] = json.loads(request.content.decode("utf-8"))
        content = "\n".join(
            [
                'data: {"choices":[{"delta":{"content":"你"}}]}',
                'data: {"choices":[{"delta":{"content":"好"}}]}',
                "data: [DONE]",
            ]
        )
        return httpx.Response(200, content=content)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIProvider(client=client)

    events = list(provider.stream_chat(make_request()))

    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "gpt-test"
    assert captured["json"]["stream"] is True
    assert captured["json"]["messages"] == [{"role": "user", "content": "你好"}]
    assert [event.content for event in events if event.type == "text"] == ["你", "好"]
    assert events[-1].type == "done"


def test_openai_provider_turns_http_error_into_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, content="bad key")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIProvider(client=client)

    with pytest.raises(ProviderError, match="OpenAI API 请求失败"):
        list(provider.stream_chat(make_request()))
