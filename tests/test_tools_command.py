from __future__ import annotations

import sys
from pathlib import Path

from mewcode.tools.base import ToolContext, run_tool
from mewcode.tools.command_tool import RunCommandTool


def context(tmp_path: Path, timeout_seconds: float = 10.0) -> ToolContext:
    return ToolContext(workspace=tmp_path, timeout_seconds=timeout_seconds)


def test_run_command_success(tmp_path: Path):
    result = run_tool(
        RunCommandTool(),
        {"command": f"{sys.executable} -c \"print('hello')\""},
        context(tmp_path),
    )

    assert result.ok is True
    assert result.data["exit_code"] == 0
    assert "hello" in result.data["stdout"]


def test_run_command_nonzero_exit(tmp_path: Path):
    result = run_tool(
        RunCommandTool(),
        {"command": f"{sys.executable} -c \"import sys; sys.exit(3)\""},
        context(tmp_path),
    )

    assert result.ok is False
    assert result.data["exit_code"] == 3


def test_run_command_timeout(tmp_path: Path):
    result = run_tool(
        RunCommandTool(),
        {"command": f"{sys.executable} -c \"import time; time.sleep(2)\""},
        context(tmp_path, timeout_seconds=0.2),
    )

    assert result.ok is False
    assert "超过" in result.error


def test_run_command_rejects_outside_cwd(tmp_path: Path):
    result = run_tool(
        RunCommandTool(),
        {"command": "echo hi", "cwd": "../outside"},
        context(tmp_path),
    )

    assert result.ok is False
    assert "工作区外" in result.error
