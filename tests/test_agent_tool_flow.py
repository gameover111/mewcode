from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path

import httpx

from mewcode.agent import stream_agent_reply
from mewcode.conversation import Conversation
from mewcode.providers.base import ChatMessage, ChatRequest, ProviderConfig, ProviderEvent, ToolCall
from mewcode.providers.openai import OpenAIProvider
from mewcode.tools.base import ToolContext
from mewcode.tools.registry import create_default_registry


class ScriptedProvider:
    def __init__(self, responses: list[list[ProviderEvent]]) -> None:
        self.responses = responses
        self.requests: list[ChatRequest] = []

    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]:
        self.requests.append(request)
        yield from self.responses.pop(0)


def config() -> ProviderConfig:
    return ProviderConfig(
        name="test",
        protocol="openai",
        model="test",
        base_url="https://example.com",
        api_key="key",
    )


def test_agent_keeps_plain_chat_path(tmp_path: Path):
    conversation = Conversation([ChatMessage(role="user", content="你好")])
    provider = ScriptedProvider(
        [[ProviderEvent(type="text", content="你好"), ProviderEvent(type="done")]]
    )

    events = list(
        stream_agent_reply(
            conversation,
            config(),
            provider,
            create_default_registry(),
            ToolContext(workspace=tmp_path),
        )
    )

    assert [event.content for event in events if event.type == "text"] == ["你好"]
    assert conversation.messages[-1].role == "assistant"
    assert provider.requests[0].tools


def test_agent_executes_tool_and_requests_final_reply(tmp_path: Path):
    (tmp_path / "README.md").write_text("MewCode readme", encoding="utf-8")
    conversation = Conversation([ChatMessage(role="user", content="读 README")])
    provider = ScriptedProvider(
        [
            [
                ProviderEvent(
                    type="tool_call",
                    tool_call=ToolCall(
                        id="call_1",
                        name="read_file",
                        arguments_json='{"path":"README.md"}',
                    ),
                )
            ],
            [ProviderEvent(type="text", content="已读取 README"), ProviderEvent(type="done")],
        ]
    )

    events = list(
        stream_agent_reply(
            conversation,
            config(),
            provider,
            create_default_registry(),
            ToolContext(workspace=tmp_path),
        )
    )

    assert [event.type for event in events] == ["tool_start", "tool_result", "text", "done"]
    assert len(provider.requests) == 2
    assert provider.requests[1].tools is None
    assert conversation.messages[-3].tool_calls[0].name == "read_file"
    assert conversation.messages[-2].role == "tool"
    assert "MewCode readme" in conversation.messages[-2].content
    assert conversation.messages[-1].content == "已读取 README"


def test_agent_handles_unknown_tool_as_structured_result(tmp_path: Path):
    conversation = Conversation([ChatMessage(role="user", content="调用不存在")])
    provider = ScriptedProvider(
        [
            [
                ProviderEvent(
                    type="tool_call",
                    tool_call=ToolCall(id="call_1", name="missing_tool", arguments_json="{}"),
                )
            ],
            [ProviderEvent(type="text", content="工具不存在"), ProviderEvent(type="done")],
        ]
    )

    list(
        stream_agent_reply(
            conversation,
            config(),
            provider,
            create_default_registry(),
            ToolContext(workspace=tmp_path),
        )
    )

    assert "工具未注册" in conversation.messages[-2].content


def test_agent_handles_invalid_json_arguments(tmp_path: Path):
    conversation = Conversation([ChatMessage(role="user", content="坏参数")])
    provider = ScriptedProvider(
        [
            [
                ProviderEvent(
                    type="tool_call",
                    tool_call=ToolCall(id="call_1", name="read_file", arguments_json="{bad"),
                )
            ],
            [ProviderEvent(type="text", content="参数错误"), ProviderEvent(type="done")],
        ]
    )

    list(
        stream_agent_reply(
            conversation,
            config(),
            provider,
            create_default_registry(),
            ToolContext(workspace=tmp_path),
        )
    )

    assert "合法 JSON" in conversation.messages[-2].content


def test_agent_stops_if_second_request_asks_for_tool(tmp_path: Path):
    conversation = Conversation([ChatMessage(role="user", content="循环")])
    provider = ScriptedProvider(
        [
            [
                ProviderEvent(
                    type="tool_call",
                    tool_call=ToolCall(
                        id="call_1",
                        name="read_file",
                        arguments_json='{"path":"README.md"}',
                    ),
                )
            ],
            [
                ProviderEvent(
                    type="tool_call",
                    tool_call=ToolCall(id="call_2", name="read_file", arguments_json="{}"),
                )
            ],
        ]
    )

    events = list(
        stream_agent_reply(
            conversation,
            config(),
            provider,
            create_default_registry(),
            ToolContext(workspace=tmp_path),
        )
    )

    assert any("只支持一次工具调用" in event.content for event in events)


def test_agent_end_to_end_with_openai_compatible_sse(tmp_path: Path):
    (tmp_path / "README.md").write_text("MewCode 工具系统", encoding="utf-8")
    captured_requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured_requests.append(body)
        if len(captured_requests) == 1:
            content = "\n".join(
                [
                    'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"read_file","arguments":"{\\"pa"}}]}}]}',
                    'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"th\\":\\"README.md\\"}"}}]},"finish_reason":"tool_calls"}]}',
                    "data: [DONE]",
                ]
            )
        else:
            assert body["messages"][-1]["role"] == "tool"
            assert "MewCode 工具系统" in body["messages"][-1]["content"]
            content = "\n".join(
                [
                    'data: {"choices":[{"delta":{"content":"总结完成"}}]}',
                    "data: [DONE]",
                ]
            )
        return httpx.Response(200, content=content)

    provider = OpenAIProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    conversation = Conversation([ChatMessage(role="user", content="读 README")])

    events = list(
        stream_agent_reply(
            conversation,
            config(),
            provider,
            create_default_registry(),
            ToolContext(workspace=tmp_path),
        )
    )

    assert len(captured_requests) == 2
    assert captured_requests[0]["tools"]
    assert "tools" not in captured_requests[1]
    assert [event.content for event in events if event.type == "text"] == ["总结完成"]
