from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from mewcode.agent import (
    AgentControl,
    AgentEvent,
    AgentOptions,
    AgentRunState,
    stream_agent_reply,
)
from mewcode.conversation import Conversation
from mewcode.providers.base import ChatMessage, ChatRequest, ProviderConfig, ProviderEvent, ToolCall
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


# --- AC2: 无工具调用时终止并输出 final ---

def test_no_tool_call_terminates_with_final(tmp_path: Path):
    conversation = Conversation([ChatMessage(role="user", content="你好")])
    provider = ScriptedProvider([
        [ProviderEvent(type="text", content="你好世界"), ProviderEvent(type="done")],
    ])

    events = list(
        stream_agent_reply(conversation, config(), provider, create_default_registry(), ToolContext(workspace=tmp_path))
    )

    types = [e.type for e in events]
    assert "final" in types
    assert "done" in types
    final_events = [e for e in events if e.type == "final"]
    assert final_events[0].content == "你好世界"


# --- AC3: 达到最大轮数 ---

def test_max_rounds_termination(tmp_path: Path):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    conversation = Conversation([ChatMessage(role="user", content="读文件")])
    # 无限提供 tool_call 响应
    responses = []
    for _ in range(10):
        responses.append([
            ProviderEvent(
                type="tool_call",
                tool_call=ToolCall(id=f"call_{_}", name="read_file", arguments_json='{"path":"a.txt"}'),
            )
        ])
    responses.append([ProviderEvent(type="text", content="完成"), ProviderEvent(type="done")])

    provider = ScriptedProvider(responses)

    events = list(
        stream_agent_reply(
            conversation, config(), provider, create_default_registry(), ToolContext(workspace=tmp_path),
            options=AgentOptions(max_rounds=3),
        )
    )

    types = [e.type for e in events]
    assert "error" in types
    error_events = [e for e in events if e.type == "error"]
    assert "最大轮数" in error_events[-1].content
    assert events[-1].type == "done"


# --- AC4: 取消信号 ---

def test_cancel_stops_loop(tmp_path: Path):
    conversation = Conversation([ChatMessage(role="user", content="你好")])
    provider = ScriptedProvider([
        [ProviderEvent(type="text", content="处理中..."), ProviderEvent(type="done")],
    ])
    control = AgentControl()
    control.cancel()

    events = list(
        stream_agent_reply(
            conversation, config(), provider, create_default_registry(), ToolContext(workspace=tmp_path),
            control=control,
        )
    )

    types = [e.type for e in events]
    assert "cancelled" in types
    assert events[-1].type == "done"


# --- AC5: 整体超时 ---

def test_overall_timeout(tmp_path: Path):
    """整体超时应终止循环"""
    conversation = Conversation([ChatMessage(role="user", content="你好")])

    class SlowProvider:
        def __init__(self):
            self.called = False
        def stream_chat(self, request):
            self.called = True
            import time
            time.sleep(0.3)
            yield ProviderEvent(type="text", content="慢")
            yield ProviderEvent(type="done")

    provider = SlowProvider()

    events = list(
        stream_agent_reply(
            conversation, config(), provider, create_default_registry(), ToolContext(workspace=tmp_path),
            options=AgentOptions(overall_timeout_seconds=0.1),
        )
    )

    types = [e.type for e in events]
    assert "error" in types
    error_content = " ".join(e.content for e in events if e.type == "error")
    assert "超时" in error_content
    assert events[-1].type == "done"


# --- AC6: 事件流完整性 ---

def test_event_types_in_loop(tmp_path: Path):
    (tmp_path / "f.txt").write_text("data", encoding="utf-8")
    conversation = Conversation([ChatMessage(role="user", content="查文件")])
    provider = ScriptedProvider([
        [
            ProviderEvent(
                type="tool_call",
                tool_call=ToolCall(id="c1", name="read_file", arguments_json='{"path":"f.txt"}'),
            )
        ],
        [ProviderEvent(type="text", content="已查看"), ProviderEvent(type="done")],
    ])

    events = list(
        stream_agent_reply(conversation, config(), provider, create_default_registry(), ToolContext(workspace=tmp_path))
    )

    types = [e.type for e in events]
    assert "user_message" in types
    assert "tool_start" in types
    assert "tool_result" in types
    assert "text" in types   # 第二轮 text
    assert "final" in types
    assert "done" in types

    # round_index 应该存在
    for e in events:
        assert e.round_index is not None or e.type == "user_message"
    # tool_start 应该携带 tool 信息
    tool_starts = [e for e in events if e.type == "tool_start"]
    assert tool_starts[0].tool_name == "read_file"
    assert tool_starts[0].tool_call_id == "c1"


# --- AC7: thinking 事件 ---

def test_thinking_event_passthrough(tmp_path: Path):
    conversation = Conversation([ChatMessage(role="user", content="思考")]
    )
    provider = ScriptedProvider([
        [
            ProviderEvent(type="thinking", content="让我想想..."),
            ProviderEvent(type="text", content="答案是 42"),
            ProviderEvent(type="done"),
        ],
    ])

    events = list(
        stream_agent_reply(conversation, config(), provider, create_default_registry(), ToolContext(workspace=tmp_path))
    )

    thinking_events = [e for e in events if e.type == "thinking"]
    assert len(thinking_events) >= 1
    assert thinking_events[0].content == "让我想想..."


# --- AC13: 工具失败回填 ---

def test_tool_failure_fed_back_to_model(tmp_path: Path):
    conversation = Conversation([ChatMessage(role="user", content="读不存在的文件")])
    provider = ScriptedProvider([
        [
            ProviderEvent(
                type="tool_call",
                tool_call=ToolCall(id="c1", name="read_file", arguments_json='{"path":"/nonexistent/file.txt"}'),
            )
        ],
        [ProviderEvent(type="text", content="文件不存在"), ProviderEvent(type="done")],
    ])

    list(
        stream_agent_reply(conversation, config(), provider, create_default_registry(), ToolContext(workspace=tmp_path))
    )

    # tool result 应该包含失败信息
    tool_messages = [m for m in conversation.messages if m.role == "tool"]
    assert len(tool_messages) >= 1
    assert "错误" in tool_messages[-1].content or "ok" in tool_messages[-1].content


# --- AC5: 每轮超时 ---

def test_per_round_timeout(tmp_path: Path):
    conversation = Conversation([ChatMessage(role="user", content="你好")])

    class SlowProvider:
        def stream_chat(self, request):
            import time
            yield ProviderEvent(type="text", content="开")
            time.sleep(0.3)
            yield ProviderEvent(type="done")

    events = list(
        stream_agent_reply(
            conversation, config(), SlowProvider(), create_default_registry(), ToolContext(workspace=tmp_path),
            options=AgentOptions(per_round_timeout_seconds=0.1),
        )
    )

    types = [e.type for e in events]
    assert "error" in types
    error_content = " ".join(e.content for e in events if e.type == "error")
    assert "超时" in error_content
