from __future__ import annotations

import json

import httpx

from mewcode.providers.base import ChatMessage, ChatRequest, ProviderConfig, ToolCall
from mewcode.providers.openai import OpenAIProvider


def config() -> ProviderConfig:
    return ProviderConfig(
        name="openai",
        protocol="openai",
        model="gpt-test",
        base_url="https://api.example.com/v1/chat/completions",
        api_key="test-key",
    )


def test_openai_provider_sends_tools_and_tool_messages():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, content="data: [DONE]\n\n")

    provider = OpenAIProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    request = ChatRequest(
        config=config(),
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "读取文件",
                    "parameters": {"type": "object"},
                },
            }
        ],
        messages=[
            ChatMessage(role="user", content="读文件"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="read_file",
                        arguments_json='{"path":"README.md"}',
                    )
                ],
            ),
            ChatMessage(role="tool", content='{"ok":true}', tool_call_id="call_1"),
        ],
    )

    list(provider.stream_chat(request))

    assert captured["json"]["tools"][0]["function"]["name"] == "read_file"
    assert captured["json"]["tool_choice"] == "auto"
    assert captured["json"]["messages"][1]["tool_calls"][0]["id"] == "call_1"
    assert captured["json"]["messages"][2]["role"] == "tool"
    assert captured["json"]["messages"][2]["tool_call_id"] == "call_1"


def test_openai_provider_parses_streaming_tool_call_fragments():
    def handler(request: httpx.Request) -> httpx.Response:
        content = "\n".join(
            [
                'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"read_file","arguments":"{\\"pa"}}]}}]}',
                'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"th\\":\\"README.md\\"}"}}]},"finish_reason":"tool_calls"}]}',
                "data: [DONE]",
            ]
        )
        return httpx.Response(200, content=content)

    provider = OpenAIProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    events = list(
        provider.stream_chat(
            ChatRequest(config=config(), messages=[ChatMessage(role="user", content="读 README")])
        )
    )

    tool_events = [event for event in events if event.type == "tool_call"]
    assert len(tool_events) == 1
    assert tool_events[0].tool_call.id == "call_1"
    assert tool_events[0].tool_call.name == "read_file"
    assert tool_events[0].tool_call.arguments_json == '{"path":"README.md"}'


def test_openai_provider_keeps_text_streaming_behavior():
    def handler(request: httpx.Request) -> httpx.Response:
        content = "\n".join(
            [
                'data: {"choices":[{"delta":{"content":"你"}}]}',
                'data: {"choices":[{"delta":{"content":"好"}}]}',
                "data: [DONE]",
            ]
        )
        return httpx.Response(200, content=content)

    provider = OpenAIProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    events = list(
        provider.stream_chat(
            ChatRequest(config=config(), messages=[ChatMessage(role="user", content="你好")])
        )
    )

    assert [event.content for event in events if event.type == "text"] == ["你", "好"]
