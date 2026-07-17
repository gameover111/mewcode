from __future__ import annotations

import time
from pathlib import Path

import pytest

from mewcode.agent import AgentControl, AgentOptions, stream_agent_reply, execute_tool_calls
from mewcode.conversation import Conversation
from mewcode.providers.base import ChatMessage, ProviderConfig, ProviderEvent, ToolCall
from mewcode.providers.base import ChatRequest
from mewcode.tools.base import ToolContext
from mewcode.tools.registry import create_default_registry
from collections.abc import Iterator


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


class SlowProvider:
    def __init__(self, delay: float = 0.5):
        self.delay = delay
        self.called = False

    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]:
        self.called = True
        time.sleep(self.delay)
        yield ProviderEvent(type="text", content="慢")
        yield ProviderEvent(type="done")


def test_control_cancel_before_loop(tmp_path: Path):
    conversation = Conversation([ChatMessage(role="user", content="你好")])
    provider = ScriptedProvider([
        [ProviderEvent(type="text", content="你好"), ProviderEvent(type="done")],
    ])
    control = AgentControl()
    control.cancel()

    events = list(
        stream_agent_reply(
            conversation, config(), provider, create_default_registry(), ToolContext(workspace=tmp_path),
            control=control,
        )
    )

    assert events[-2].type == "cancelled"
    assert events[-1].type == "done"


def test_cancel_during_provider_stream(tmp_path: Path):
    conversation = Conversation([ChatMessage(role="user", content="你好")])

    class InterruptibleProvider:
        def __init__(self):
            self.started = False
        def stream_chat(self, request):
            self.started = True
            yield ProviderEvent(type="text", content="一段文字")
            yield ProviderEvent(type="done")

    control = AgentControl()
    events = []
    for event in stream_agent_reply(
        conversation, config(), InterruptibleProvider(), create_default_registry(), ToolContext(workspace=tmp_path),
        control=control,
    ):
        events.append(event)
        if event.type == "text":
            control.cancel()

    assert "cancelled" in [e.type for e in events]


def test_overall_timeout_terminates_loop(tmp_path: Path):
    conversation = Conversation([ChatMessage(role="user", content="你好")])

    events = list(
        stream_agent_reply(
            conversation, config(), SlowProvider(delay=0.3), create_default_registry(), ToolContext(workspace=tmp_path),
            options=AgentOptions(overall_timeout_seconds=0.1),
        )
    )

    assert any("超时" in e.content for e in events if e.type == "error")
    assert events[-1].type == "done"


def test_overall_timeout_across_rounds(tmp_path: Path):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    conversation = Conversation([ChatMessage(role="user", content="读文件")])

    class MultiRoundSlowProvider:
        def __init__(self):
            self.round = 0
        def stream_chat(self, request):
            self.round += 1
            time.sleep(0.2)
            if self.round == 1:
                yield ProviderEvent(
                    type="tool_call",
                    tool_call=ToolCall(id="c1", name="read_file", arguments_json='{"path":"a.txt"}'),
                )
            else:
                yield ProviderEvent(type="text", content="完成"), ProviderEvent(type="done")

    events = list(
        stream_agent_reply(
            conversation, config(), MultiRoundSlowProvider(), create_default_registry(), ToolContext(workspace=tmp_path),
            options=AgentOptions(overall_timeout_seconds=0.15),
        )
    )

    error_events = [e for e in events if e.type == "error" and "超时" in e.content]
    assert len(error_events) >= 1


def test_agent_run_state_initial_values():
    state = type("State", (), {"round_index": 0, "terminate_reason": None, "started_at": 0})()
    assert state.round_index == 0
    assert state.terminate_reason is None


def test_agent_options_defaults():
    opts = AgentOptions()
    assert opts.max_rounds == 8
    assert opts.plan_only is False
    assert opts.overall_timeout_seconds is None
    assert opts.per_round_timeout_seconds is None


def test_agent_control_defaults():
    ctrl = AgentControl()
    assert ctrl.cancelled is False
    ctrl.cancel()
    assert ctrl.cancelled is True
