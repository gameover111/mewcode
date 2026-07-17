from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mewcode.tools.base import ToolContext, ToolError, ToolResult
from mewcode.tools.security import ensure_not_private, truncate_text


SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
DEFAULT_MAX_RESULTS = 100


class FindFilesTool:
    name = "find_files"
    description = "按 glob 模式查找工作区内文件。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "glob 文件模式，例如 tests/test_*.py。"},
            "max_results": {"type": "integer", "description": "最多返回多少个结果。"},
        },
        "required": ["pattern"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        pattern = _required_str(arguments, "pattern")
        max_results = _max_results(arguments)
        results: list[str] = []
        truncated = False

        for path in sorted(context.workspace.glob(pattern)):
            if _is_skipped(path, context.workspace) or not path.is_file():
                continue
            results.append(_relative(path, context.workspace))
            if len(results) >= max_results:
                truncated = True
                break

        return ToolResult(
            ok=True,
            summary=f"找到 {len(results)} 个文件。",
            data={"files": results, "truncated": truncated},
        )


class SearchCodeTool:
    name = "search_code"
    description = "在工作区文本文件中搜索字符串或正则表达式。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "要搜索的文本或正则表达式。"},
            "regex": {"type": "boolean", "description": "是否按正则表达式搜索。"},
            "pattern": {"type": "string", "description": "限制搜索的 glob 文件模式，默认 **/*。"},
            "max_results": {"type": "integer", "description": "最多返回多少个匹配项。"},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        query = _required_str(arguments, "query")
        pattern = arguments.get("pattern") or "**/*"
        if not isinstance(pattern, str):
            raise ToolError("参数 pattern 必须是字符串。")
        use_regex = bool(arguments.get("regex", False))
        max_results = _max_results(arguments)
        compiled = re.compile(query) if use_regex else None

        matches: list[dict[str, Any]] = []
        truncated = False
        for path in sorted(context.workspace.glob(pattern)):
            if _is_skipped(path, context.workspace) or not path.is_file():
                continue
            try:
                ensure_not_private(path)
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError, ToolError):
                continue

            for line_number, line in enumerate(lines, start=1):
                if _line_matches(line, query, compiled):
                    text, line_truncated = truncate_text(line, 500)
                    matches.append(
                        {
                            "path": _relative(path, context.workspace),
                            "line": line_number,
                            "text": text,
                            "truncated": line_truncated,
                        }
                    )
                    if len(matches) >= max_results:
                        truncated = True
                        return ToolResult(
                            ok=True,
                            summary=f"找到 {len(matches)} 个匹配项。",
                            data={"matches": matches, "truncated": truncated},
                        )

        return ToolResult(
            ok=True,
            summary=f"找到 {len(matches)} 个匹配项。",
            data={"matches": matches, "truncated": truncated},
        )


def _required_str(arguments: dict[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str):
        raise ToolError(f"参数 {name} 必须是字符串。")
    return value


def _max_results(arguments: dict[str, Any]) -> int:
    value = arguments.get("max_results", DEFAULT_MAX_RESULTS)
    if not isinstance(value, int) or value <= 0:
        raise ToolError("参数 max_results 必须是正整数。")
    return value


def _is_skipped(path: Path, workspace: Path) -> bool:
    try:
        parts = path.resolve().relative_to(workspace.resolve()).parts
    except ValueError:
        return True
    return any(part in SKIP_DIRS for part in parts)


def _relative(path: Path, workspace: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def _line_matches(line: str, query: str, compiled: re.Pattern[str] | None) -> bool:
    if compiled is not None:
        return compiled.search(line) is not None
    return query in line

