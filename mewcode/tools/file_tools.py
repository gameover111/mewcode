from __future__ import annotations

from typing import Any

from mewcode.tools.base import ToolContext, ToolError, ToolResult
from mewcode.tools.security import ensure_not_private, resolve_workspace_path, truncate_text


class ReadFileTool:
    name = "read_file"
    description = "读取工作区内的文本文件内容。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "要读取的文件路径，必须位于工作区内。"}
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        path = _required_str(arguments, "path")
        resolved = resolve_workspace_path(context.workspace, path)
        ensure_not_private(resolved)
        if resolved.is_dir():
            raise ToolError(f"路径是目录，不是文件：{path}")
        if not resolved.exists():
            raise ToolError(f"文件不存在：{path}")

        content = resolved.read_text(encoding="utf-8")
        content, truncated = truncate_text(content, context.max_output_chars)
        return ToolResult(
            ok=True,
            summary=f"已读取文件：{path}",
            data={"path": path, "content": content, "truncated": truncated},
        )


class WriteFileTool:
    name = "write_file"
    description = "在工作区内写入文本文件，会创建父目录并覆盖已有内容。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "要写入的文件路径，必须位于工作区内。"},
            "content": {"type": "string", "description": "要写入的文本内容。"},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        path = _required_str(arguments, "path")
        content = _required_str(arguments, "content")
        resolved = resolve_workspace_path(context.workspace, path)
        ensure_not_private(resolved)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return ToolResult(
            ok=True,
            summary=f"已写入文件：{path}",
            data={"path": path, "chars": len(content)},
        )


class ReplaceInFileTool:
    name = "replace_in_file"
    description = "在工作区内修改文本文件，只在原文片段唯一匹配时替换。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "要修改的文件路径，必须位于工作区内。"},
            "old_text": {"type": "string", "description": "要替换的原文片段，必须唯一匹配。"},
            "new_text": {"type": "string", "description": "替换后的文本。"},
        },
        "required": ["path", "old_text", "new_text"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        path = _required_str(arguments, "path")
        old_text = _required_str(arguments, "old_text")
        new_text = _required_str(arguments, "new_text")
        if old_text == "":
            raise ToolError("old_text 不能为空。")

        resolved = resolve_workspace_path(context.workspace, path)
        ensure_not_private(resolved)
        if resolved.is_dir():
            raise ToolError(f"路径是目录，不是文件：{path}")
        if not resolved.exists():
            raise ToolError(f"文件不存在：{path}")

        content = resolved.read_text(encoding="utf-8")
        count = content.count(old_text)
        if count == 0:
            raise ToolError("原文片段未匹配到，无法替换。")
        if count > 1:
            raise ToolError(f"原文片段匹配到 {count} 次，必须唯一匹配。")

        updated = content.replace(old_text, new_text, 1)
        resolved.write_text(updated, encoding="utf-8")
        return ToolResult(
            ok=True,
            summary=f"已修改文件：{path}",
            data={
                "path": path,
                "old_chars": len(old_text),
                "new_chars": len(new_text),
            },
        )


def _required_str(arguments: dict[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str):
        raise ToolError(f"参数 {name} 必须是字符串。")
    return value
