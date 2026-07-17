from __future__ import annotations

import time
from pathlib import Path

import pytest

from mewcode.agent import (
    ToolExecutionHooks,
    execute_tool_calls,
    tool_kind,
)
from mewcode.providers.base import ToolCall
from mewcode.tools.base import ToolContext, ToolResult
from mewcode.tools.registry import create_default_registry


@pytest.fixture
def registry():
    return create_default_registry()


@pytest.fixture
def context(tmp_path):
    return ToolContext(workspace=tmp_path)


def test_tool_kind_classification():
    assert tool_kind("read_file") == "read"
    assert tool_kind("find_files") == "read"
    assert tool_kind("search_code") == "read"
    assert tool_kind("write_file") == "write"
    assert tool_kind("replace_in_file") == "write"
    assert tool_kind("run_command") == "write"
    assert tool_kind("unknown_tool") == "write"  # 默认保守


def test_empty_tool_calls(registry, context):
    assert execute_tool_calls([], registry, context) == []


def test_unknown_tool_is_structured_error(registry, context):
    results = execute_tool_calls(
        [ToolCall(id="c1", name="no_such_tool", arguments_json="{}")],
        registry, context,
    )
    assert len(results) == 1
    tc, tr = results[0]
    assert tc.id == "c1"
    assert tr.ok is False
    assert "未注册" in tr.error


def test_single_read_tool(tmp_path, registry):
    (tmp_path / "hello.txt").write_text("hello", encoding="utf-8")
    context = ToolContext(workspace=tmp_path)
    results = execute_tool_calls(
        [ToolCall(id="c1", name="read_file", arguments_json='{"path":"hello.txt"}')],
        registry, context,
    )
    assert len(results) == 1
    tc, tr = results[0]
    assert tc.id == "c1"
    assert tr.ok is True
    assert "hello" in tr.data.get("content", "")


def test_read_tools_run_concurrently(tmp_path, registry):
    (tmp_path / "a.txt").write_text("aaa", encoding="utf-8")
    (tmp_path / "b.txt").write_text("bbb", encoding="utf-8")
    context = ToolContext(workspace=tmp_path, timeout_seconds=5.0)

    start = time.monotonic()
    results = execute_tool_calls(
        [
            ToolCall(id="c1", name="read_file", arguments_json='{"path":"a.txt"}'),
            ToolCall(id="c2", name="read_file", arguments_json='{"path":"b.txt"}'),
        ],
        registry, context,
    )
    elapsed = time.monotonic() - start
    assert len(results) == 2
    # 两个读工具都应该成功
    for tc, tr in results:
        assert tr.ok is True


def test_write_tools_run_serially(tmp_path, registry):
    context = ToolContext(workspace=tmp_path)
    results = execute_tool_calls(
        [
            ToolCall(id="c1", name="write_file", arguments_json='{"path":"a.txt","content":"aaa"}'),
            ToolCall(id="c2", name="write_file", arguments_json='{"path":"b.txt","content":"bbb"}'),
        ],
        registry, context,
    )
    assert len(results) == 2
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "aaa"
    assert (tmp_path / "b.txt").read_text(encoding="utf-8") == "bbb"


def test_results_ordered_by_original_indices(tmp_path, registry):
    """混合读写的工具结果按原始顺序返回"""
    (tmp_path / "a.txt").write_text("aaa", encoding="utf-8")
    context = ToolContext(workspace=tmp_path)

    results = execute_tool_calls(
        [
            ToolCall(id="c1", name="write_file", arguments_json='{"path":"z.txt","content":"zzz"}'),
            ToolCall(id="c2", name="read_file", arguments_json='{"path":"a.txt"}'),
        ],
        registry, context,
    )
    # 结果应该按原始顺序 [write, read]
    assert len(results) == 2
    assert results[0][0].id == "c1"  # write first
    assert results[1][0].id == "c2"  # read second
    assert results[1][1].ok is True


def test_before_hook_can_skip_execution(registry, context):
    hook_calls = []

    def before(tc):
        hook_calls.append(tc.id)
        return ToolResult(ok=True, summary="hook 跳过", data={"content": "fake"})

    hooks = ToolExecutionHooks(before_tool=before)
    results = execute_tool_calls(
        [ToolCall(id="c1", name="read_file", arguments_json='{"path":"nonexistent.md"}')],
        registry, context, hooks=hooks,
    )
    assert len(results) == 1
    tc, tr = results[0]
    assert tr.ok is True
    assert tr.summary == "hook 跳过"
    assert hook_calls == ["c1"]


def test_after_hook_is_called(registry, context):
    after_calls = []

    def after(tc, tr):
        after_calls.append((tc.id, tr.ok))

    hooks = ToolExecutionHooks(after_tool=after)
    results = execute_tool_calls(
        [ToolCall(id="c1", name="read_file", arguments_json='{"path":"nonexistent.md"}')],
        registry, context, hooks=hooks,
    )
    assert after_calls == [("c1", False)]


def test_bad_json_arguments(registry, context):
    results = execute_tool_calls(
        [ToolCall(id="c1", name="read_file", arguments_json="{bad json}")],
        registry, context,
    )
    assert results[0][1].ok is False
    assert "合法 JSON" in results[0][1].summary
