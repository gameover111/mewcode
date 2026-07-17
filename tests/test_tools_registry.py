from __future__ import annotations

import pytest

from mewcode.tools.base import ToolError
from mewcode.tools.file_tools import ReadFileTool
from mewcode.tools.registry import ToolRegistry, create_default_registry


def test_default_registry_contains_six_core_tools():
    registry = create_default_registry()

    assert registry.names() == [
        "read_file",
        "write_file",
        "replace_in_file",
        "run_command",
        "find_files",
        "search_code",
    ]


def test_registry_gets_tool_by_name():
    registry = create_default_registry()

    assert registry.get("read_file").name == "read_file"
    assert registry.get("missing") is None


def test_registry_rejects_duplicate_name():
    registry = ToolRegistry()
    registry.register(ReadFileTool())

    with pytest.raises(ToolError, match="已注册"):
        registry.register(ReadFileTool())


def test_registry_outputs_openai_tool_schema():
    registry = create_default_registry()

    tools = registry.to_openai_tools()

    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "read_file"
    assert "description" in tools[0]["function"]
    assert tools[0]["function"]["parameters"]["type"] == "object"
