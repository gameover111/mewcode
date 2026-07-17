from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ToolContext:
    workspace: Path
    timeout_seconds: float = 10.0
    max_output_chars: int = 20000


class ToolError(Exception):
    """工具可预期错误，会作为结构化结果返回给模型。"""


class Tool(Protocol):
    name: str
    description: str
    parameters_schema: dict[str, Any]

    def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        ...


def run_tool(tool: Tool, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
    try:
        return tool.execute(arguments, context)
    except ToolError as exc:
        return ToolResult(ok=False, summary=f"工具 {tool.name} 执行失败", error=str(exc))
    except Exception as exc:
        return ToolResult(
            ok=False,
            summary=f"工具 {tool.name} 执行异常",
            error=f"{type(exc).__name__}: {exc}",
        )

