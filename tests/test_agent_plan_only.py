from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from mewcode.agent import (
    AgentOptions,
    execute_tool_calls,
    stream_agent_reply,
    tool_kind,
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


# --- AC10: plan-only 读类工具可执行 ---

def test_plan_only_read_tools_execute(tmp_path: Path):
    (tmp_path / "plan.txt").write_text("plan content", encoding="utf-8")
    context = ToolContext(workspace=tmp_path)
    registry = create_default_registry()

    results = execute_tool_calls(
        [ToolCall(id="c1", name="read_file", arguments_json='{"path":"plan.txt"}')],
        registry, context, plan_only=True,
    )
    assert len(results) == 1
    tc, tr = results[0]
    assert tr.ok is True
    assert "plan content" in tr.data.get("content", "")


# --- AC11: plan-only 写类工具被拦截 ---

def test_plan_only_write_tools_intercepted(tmp_path: Path):
    context = ToolContext(workspace=tmp_path)
    registry = create_default_registry()

    results = execute_tool_calls(
        [ToolCall(id="c1", name="write_file", arguments_json='{"path":"secret.txt","content":"hack"}')],
        registry, context, plan_only=True,
    )

    assert len(results) == 1
    tc, tr = results[0]
    assert tr.ok is False
    assert "plan-only" in tr.summary
    # 文件不应该被实际写入
    assert not (tmp_path / "secret.txt").exists()


def test_plan_only_prevents_side_effects(tmp_path: Path):
    """plan-only 模式下所有写工具都不应有副作用"""
    context = ToolContext(workspace=tmp_path)
    registry = create_default_registry()

    for tool_name, args in [
        ("write_file", '{"path":"x.txt","content":"x"}'),
        ("replace_in_file", '{"path":"x.txt","match":"x","replacement":"y"}'),
        ("run_command", '{"command":"echo hacked"}'),
    ]:
        results = execute_tool_calls(
            [ToolCall(id="c", name=tool_name, arguments_json=args)],
            registry, context, plan_only=True,
        )
        assert results[0][1].ok is False
        assert "plan-only" in results[0][1].summary


# --- AC12: plan-only 端到端 ---

def test_plan_only_e2e_requires_approval(tmp_path: Path):
    """plan-only 模式下 Agent Loop 应该正常处理读工具并进入下一轮"""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# main file", encoding="utf-8")
    conversation = Conversation([ChatMessage(role="user", content="读 main.py 然后写一个测试文件")])

    # 第一轮：读工具（plan-only 允许）
    # 第二轮：写工具被拦截 → 回填结果
    # 第三轮：模型给出最终计划
    provider = ScriptedProvider([
        [
            ProviderEvent(
                type="tool_call",
                tool_call=ToolCall(id="c1", name="read_file", arguments_json='{"path":"src/main.py"}'),
            )
        ],
        [
            ProviderEvent(
                type="tool_call",
                tool_call=ToolCall(id="c2", name="write_file", arguments_json='{"path":"src/test_main.py","content":"# test"}'),
            )
        ],
        [ProviderEvent(type="text", content="计划：创建测试文件 src/test_main.py，需要关闭 --plan-only"), ProviderEvent(type="done")],
    ])

    events = list(
        stream_agent_reply(
            conversation, config(), provider, create_default_registry(), ToolContext(workspace=tmp_path),
            options=AgentOptions(plan_only=True, max_rounds=5),
        )
    )

    types = [e.type for e in events]
    assert "tool_start" in types
    assert "tool_result" in types
    assert "final" in types
    # 写文件不应该实际被执行
    assert not (tmp_path / "src" / "test_main.py").exists()
