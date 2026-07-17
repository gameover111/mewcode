from __future__ import annotations

from pathlib import Path

from mewcode.tools.base import ToolContext, run_tool
from mewcode.tools.file_tools import ReadFileTool, ReplaceInFileTool, WriteFileTool


def context(tmp_path: Path, max_output_chars: int = 20000) -> ToolContext:
    return ToolContext(workspace=tmp_path, max_output_chars=max_output_chars)


def test_read_file_reads_text(tmp_path: Path):
    (tmp_path / "hello.txt").write_text("hello", encoding="utf-8")

    result = run_tool(ReadFileTool(), {"path": "hello.txt"}, context(tmp_path))

    assert result.ok is True
    assert result.data["content"] == "hello"
    assert result.data["truncated"] is False


def test_read_file_truncates_output(tmp_path: Path):
    (tmp_path / "hello.txt").write_text("abcdef", encoding="utf-8")

    result = run_tool(ReadFileTool(), {"path": "hello.txt"}, context(tmp_path, max_output_chars=3))

    assert result.ok is True
    assert result.data["content"] == "abc"
    assert result.data["truncated"] is True


def test_read_file_rejects_env(tmp_path: Path):
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")

    result = run_tool(ReadFileTool(), {"path": ".env"}, context(tmp_path))

    assert result.ok is False
    assert "隐私文件" in result.error


def test_read_file_rejects_outside_path(tmp_path: Path):
    result = run_tool(ReadFileTool(), {"path": "../outside.txt"}, context(tmp_path))

    assert result.ok is False
    assert "工作区外" in result.error


def test_read_file_rejects_directory(tmp_path: Path):
    (tmp_path / "dir").mkdir()

    result = run_tool(ReadFileTool(), {"path": "dir"}, context(tmp_path))

    assert result.ok is False
    assert "目录" in result.error


def test_write_file_creates_file(tmp_path: Path):
    result = run_tool(WriteFileTool(), {"path": "a/b.txt", "content": "hello"}, context(tmp_path))

    assert result.ok is True
    assert (tmp_path / "a" / "b.txt").read_text(encoding="utf-8") == "hello"


def test_write_file_overwrites_file(tmp_path: Path):
    target = tmp_path / "a.txt"
    target.write_text("old", encoding="utf-8")

    result = run_tool(WriteFileTool(), {"path": "a.txt", "content": "new"}, context(tmp_path))

    assert result.ok is True
    assert target.read_text(encoding="utf-8") == "new"


def test_write_file_rejects_outside_path(tmp_path: Path):
    result = run_tool(WriteFileTool(), {"path": "../x.txt", "content": "x"}, context(tmp_path))

    assert result.ok is False
    assert "工作区外" in result.error


def test_write_file_rejects_env(tmp_path: Path):
    result = run_tool(WriteFileTool(), {"path": ".env", "content": "SECRET=1"}, context(tmp_path))

    assert result.ok is False
    assert "隐私文件" in result.error


def test_replace_in_file_replaces_unique_text(tmp_path: Path):
    target = tmp_path / "a.txt"
    target.write_text("hello old world", encoding="utf-8")

    result = run_tool(
        ReplaceInFileTool(),
        {"path": "a.txt", "old_text": "old", "new_text": "new"},
        context(tmp_path),
    )

    assert result.ok is True
    assert target.read_text(encoding="utf-8") == "hello new world"


def test_replace_in_file_reports_missing_text(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")

    result = run_tool(
        ReplaceInFileTool(),
        {"path": "a.txt", "old_text": "missing", "new_text": "new"},
        context(tmp_path),
    )

    assert result.ok is False
    assert "未匹配" in result.error


def test_replace_in_file_reports_multiple_matches(tmp_path: Path):
    (tmp_path / "a.txt").write_text("old old", encoding="utf-8")

    result = run_tool(
        ReplaceInFileTool(),
        {"path": "a.txt", "old_text": "old", "new_text": "new"},
        context(tmp_path),
    )

    assert result.ok is False
    assert "必须唯一匹配" in result.error


def test_replace_in_file_rejects_env(tmp_path: Path):
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")

    result = run_tool(
        ReplaceInFileTool(),
        {"path": ".env", "old_text": "SECRET", "new_text": "PUBLIC"},
        context(tmp_path),
    )

    assert result.ok is False
    assert "隐私文件" in result.error
