from __future__ import annotations

from pathlib import Path

from mewcode.tools.base import ToolContext, ToolError, ToolResult, run_tool


class SuccessTool:
    name = "success"
    description = "成功工具"
    parameters_schema = {"type": "object"}

    def execute(self, arguments, context):
        return ToolResult(ok=True, summary="完成", data={"value": arguments["value"]})


class ExpectedErrorTool:
    name = "expected_error"
    description = "预期错误工具"
    parameters_schema = {"type": "object"}

    def execute(self, arguments, context):
        raise ToolError("参数不对")


class UnexpectedErrorTool:
    name = "unexpected_error"
    description = "异常工具"
    parameters_schema = {"type": "object"}

    def execute(self, arguments, context):
        raise RuntimeError("炸了")


def test_run_tool_success(tmp_path: Path):
    result = run_tool(SuccessTool(), {"value": 42}, ToolContext(workspace=tmp_path))

    assert result.ok is True
    assert result.data["value"] == 42


def test_run_tool_expected_error(tmp_path: Path):
    result = run_tool(ExpectedErrorTool(), {}, ToolContext(workspace=tmp_path))

    assert result.ok is False
    assert result.error == "参数不对"


def test_run_tool_unexpected_error(tmp_path: Path):
    result = run_tool(UnexpectedErrorTool(), {}, ToolContext(workspace=tmp_path))

    assert result.ok is False
    assert "RuntimeError" in result.error

