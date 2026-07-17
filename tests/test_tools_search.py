from __future__ import annotations

from pathlib import Path

from mewcode.tools.base import ToolContext, run_tool
from mewcode.tools.search_tools import FindFilesTool, SearchCodeTool


def context(tmp_path: Path) -> ToolContext:
    return ToolContext(workspace=tmp_path)


def test_find_files_matches_glob(tmp_path: Path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "helper.txt").write_text("", encoding="utf-8")

    result = run_tool(FindFilesTool(), {"pattern": "tests/test_*.py"}, context(tmp_path))

    assert result.ok is True
    assert result.data["files"] == ["tests/test_a.py"]


def test_find_files_skips_cache_dirs(tmp_path: Path):
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.py").write_text("", encoding="utf-8")

    result = run_tool(FindFilesTool(), {"pattern": "**/*.py"}, context(tmp_path))

    assert result.data["files"] == []


def test_find_files_marks_truncated(tmp_path: Path):
    for index in range(3):
        (tmp_path / f"{index}.py").write_text("", encoding="utf-8")

    result = run_tool(FindFilesTool(), {"pattern": "*.py", "max_results": 2}, context(tmp_path))

    assert len(result.data["files"]) == 2
    assert result.data["truncated"] is True


def test_search_code_finds_plain_text(tmp_path: Path):
    (tmp_path / "a.py").write_text("hello\nneedle here\n", encoding="utf-8")

    result = run_tool(SearchCodeTool(), {"query": "needle"}, context(tmp_path))

    assert result.ok is True
    assert result.data["matches"][0]["path"] == "a.py"
    assert result.data["matches"][0]["line"] == 2


def test_search_code_finds_regex(tmp_path: Path):
    (tmp_path / "a.py").write_text("abc123\n", encoding="utf-8")

    result = run_tool(SearchCodeTool(), {"query": r"abc\d+", "regex": True}, context(tmp_path))

    assert len(result.data["matches"]) == 1


def test_search_code_respects_pattern(tmp_path: Path):
    (tmp_path / "a.py").write_text("needle\n", encoding="utf-8")
    (tmp_path / "a.txt").write_text("needle\n", encoding="utf-8")

    result = run_tool(SearchCodeTool(), {"query": "needle", "pattern": "*.txt"}, context(tmp_path))

    assert [match["path"] for match in result.data["matches"]] == ["a.txt"]


def test_search_code_marks_truncated(tmp_path: Path):
    (tmp_path / "a.py").write_text("needle\nneedle\n", encoding="utf-8")

    result = run_tool(SearchCodeTool(), {"query": "needle", "max_results": 1}, context(tmp_path))

    assert len(result.data["matches"]) == 1
    assert result.data["truncated"] is True
