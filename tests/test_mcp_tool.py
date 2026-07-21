from __future__ import annotations

import json
from pathlib import Path

import pytest

from mewcode.mcp.tool import McpTool, adapt_tool, _collect_text_content, call_timeout
from mewcode.tools.base import ToolContext, ToolResult


class _FakeTool:
    def __init__(self, name=None, description=None, input_schema=None, annotations=None):
        self.name = name or "my-tool"
        self.description = description or "A test tool"
        self.inputSchema = input_schema or {"type": "object", "properties": {"x": {"type": "string"}}}
        self.annotations = annotations


class _FakeContent:
    def __init__(self, type="text", text="hello world"):
        self.type = type
        self.text = text


class _CallResult:
    def __init__(self, content=None, is_error=False):
        self.content = content or [_FakeContent()]
        self.isError = is_error


class _FakeSession:
    def __init__(self, result=None, raise_err=None):
        self._result = result or _CallResult()
        self._raise = raise_err

    async def call_tool(self, name, arguments):
        if self._raise:
            raise self._raise
        return self._result


def test_adapt_tool_naming():
    fake = _FakeTool(name="read-file")
    tool = adapt_tool("github", fake, _FakeSession())
    assert tool is not None
    assert tool.full_name == "mcp__github__read-file"
    assert tool.name == "mcp__github__read-file"


def test_adapt_tool_invalid_name():
    fake = _FakeTool(name="bad/tool/name")
    tool = adapt_tool("srv", fake, _FakeSession())
    assert tool is None


def test_adapt_tool_schema():
    schema = {"type": "object", "properties": {"path": {"type": "string"}}}
    fake = _FakeTool(input_schema=schema)
    tool = adapt_tool("srv", fake, _FakeSession())
    assert tool is not None
    assert tool.parameters_schema == schema


def test_adapt_tool_read_only_hint():
    class Annotations:
        readOnlyHint = True
    fake = _FakeTool(annotations=Annotations())
    tool = adapt_tool("srv", fake, _FakeSession())
    assert tool is not None
    assert tool.read_only is True


def test_adapt_tool_no_read_only():
    fake = _FakeTool()
    tool = adapt_tool("srv", fake, _FakeSession())
    assert tool is not None
    assert tool.read_only is False


def test_mcp_tool_execute_success():
    session = _FakeSession()
    tool = McpTool(
        full_name="mcp__demo__echo",
        remote_name="echo",
        description="Echo",
        parameters_schema={"type": "object"},
        read_only=False,
        caller=session,
    )
    result = tool.execute({"msg": "hi"}, ToolContext(workspace=Path(".")))
    assert result.ok is True
    assert "hello world" in result.data.get("text", "")


def test_mcp_tool_execute_error():
    session = _FakeSession(result=_CallResult(is_error=True, content=[_FakeContent(text="boom")]))
    tool = McpTool("mcp__demo__bad", "bad", "Bad", {"type": "object"}, False, session)
    result = tool.execute({}, ToolContext(workspace=Path(".")))
    assert result.ok is False
    assert "boom" in (result.error or "")


def test_mcp_tool_execute_exception():
    session = _FakeSession(raise_err=RuntimeError("connection lost"))
    tool = McpTool("mcp__demo__err", "err", "Err", {"type": "object"}, False, session)
    result = tool.execute({}, ToolContext(workspace=Path(".")))
    assert result.ok is False


def test_mcp_tool_execute_timeout():
    import asyncio
    import mewcode.mcp.tool as mt
    async def slow(_name, _args):
        await asyncio.sleep(999)
    session = _FakeSession()
    session.call_tool = slow
    tool = McpTool("mcp__demo__slow", "slow", "Slow", {"type": "object"}, False, session)
    old_timeout = mt.call_timeout
    mt.call_timeout = 0.01
    try:
        result = tool.execute({}, ToolContext(workspace=Path(".")))
        assert result.ok is False
    finally:
        mt.call_timeout = old_timeout


def test_collect_text_content_multi():
    class Block:
        def __init__(self, typ, text):
            self.type = typ
            self.text = text
    result = _CallResult(content=[
        Block("text", "line1"),
        Block("text", "line2"),
    ])
    text = _collect_text_content("test", result)
    assert text == "line1\nline2"
