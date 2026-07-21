from __future__ import annotations

import asyncio
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from mewcode.tools.base import ToolContext, ToolResult


call_timeout: float = 30.0


class CallerSession(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        ...


@dataclass
class McpTool:
    full_name: str
    remote_name: str
    description: str
    parameters_schema: dict[str, Any]
    read_only: bool
    caller: CallerSession
    loop: asyncio.AbstractEventLoop | None = None

    @property
    def name(self) -> str:
        return self.full_name

    def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            result = _run_coroutine_sync(self._execute_async(arguments or None), self.loop)
            return result
        except Exception as exc:
            return ToolResult(
                ok=False,
                summary=f"MCP 工具 {self.full_name} 调用失败",
                error=f"MCP 工具调用失败: {exc}",
            )

    async def _execute_async(self, arguments: dict[str, Any] | None) -> ToolResult:
        try:
            result = await asyncio.wait_for(
                self.caller.call_tool(self.remote_name, arguments),
                timeout=call_timeout,
            )
        except asyncio.TimeoutError:
            return ToolResult(
                ok=False,
                summary=f"MCP 工具 {self.full_name} 调用超时",
                error="MCP 工具调用超时 (30s)",
            )
        except Exception as exc:
            return ToolResult(
                ok=False,
                summary=f"MCP 工具 {self.full_name} 调用失败",
                error=f"MCP 工具调用失败: {exc}",
            )

        text = _collect_text_content(self.full_name, result)
        is_error = bool(getattr(result, "isError", False))
        return ToolResult(
            ok=not is_error,
            summary=f"MCP 工具 {self.full_name} {'执行失败' if is_error else '执行完成'}",
            data={"text": text},
            error=text if is_error else None,
        )


_VALID_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_non_text_warn_once: set[str] = set()


def adapt_tool(server_name: str, tool: Any, session: CallerSession, loop: asyncio.AbstractEventLoop | None = None) -> McpTool | None:
    remote_name = str(getattr(tool, "name", ""))
    full_name = f"mcp__{server_name}__{remote_name}"
    if not _VALID_NAME.fullmatch(full_name):
        print(
            f"[mcp] warn: skip tool {full_name}: name contains illegal characters",
            file=sys.stderr,
        )
        return None

    description = str(getattr(tool, "description", "") or f"来自 MCP server {server_name} 的工具 {remote_name}")
    raw_schema = getattr(tool, "inputSchema", None)
    parameters = dict(raw_schema) if isinstance(raw_schema, dict) and raw_schema else {"type": "object"}
    annotations = getattr(tool, "annotations", None)
    read_only = bool(annotations and getattr(annotations, "readOnlyHint", False) is True)

    return McpTool(
        full_name=full_name,
        remote_name=remote_name,
        description=description,
        parameters_schema=parameters,
        read_only=read_only,
        caller=session,
        loop=loop,
    )


def _collect_text_content(full_name: str, result: Any) -> str:
    texts: list[str] = []
    saw_non_text = False
    for block in getattr(result, "content", []) or []:
        block_type = getattr(block, "type", None)
        if block_type is None and isinstance(block, dict):
            block_type = block.get("type")
        if block_type == "text":
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            texts.append(str(text or ""))
        else:
            saw_non_text = True
    if saw_non_text and full_name not in _non_text_warn_once:
        _non_text_warn_once.add(full_name)
        print(
            f"[mcp] warn: tool {full_name} returned non-text content blocks (dropped)",
            file=sys.stderr,
        )
    return "\n".join(texts)


def _run_coroutine_sync(coro, loop: asyncio.AbstractEventLoop | None) -> ToolResult:
    if loop is not None and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=call_timeout + 1)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result_box: list[ToolResult] = []
    error_box: list[BaseException] = []

    def runner() -> None:
        try:
            result_box.append(asyncio.run(coro))
        except BaseException as exc:
            error_box.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(call_timeout + 1)
    if thread.is_alive():
        return ToolResult(
            ok=False,
            summary="MCP 工具调用超时",
            error="MCP 工具调用超时 (30s)",
        )
    if error_box:
        raise error_box[0]
    return result_box[0]
