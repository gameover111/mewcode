# -*- coding: utf-8 -*-
"""ch8 上下文管理 —— 恢复段构造（F15/F16/F17/F18）"""
from __future__ import annotations

from mewcode.compact.const import RECOVERY_TOKENS_PER_FILE
from mewcode.compact.state import FileReadRecord
from mewcode.compact.token import estimate_tokens

BOUNDARY_NOTICE = (
    "<system-reminder>\n"
    "注意：上文中部分工具结果已被截断，早期对话历史已被摘要替换。\n"
    "如需查看被截断的完整文件内容，请使用文件读取工具重新读取对应路径。\n"
    "如需回顾已摘要的历史细节，请使用 search_code / read_file 获取最新状态。\n"
    "请不要根据摘要内容脑补不存在的代码或文件内容。\n"
    "</system-reminder>"
)


def render_file_block(record: FileReadRecord, token_budget: int = RECOVERY_TOKENS_PER_FILE) -> str:
    """渲染单个文件快照（F16）。

    token_budget 以内保留完整内容；超出时保留头部并追加 (content truncated) 标注。
    """
    from mewcode.compact.const import ESTIMATE_CHARS_PER_TOKEN

    content = record.content
    max_chars = int(token_budget * ESTIMATE_CHARS_PER_TOKEN)
    path_line = f"## 最近读取的文件：{record.path}"

    if len(content.encode("utf-8")) <= max_chars:
        return f"{path_line}\n\n```\n{content}\n```"

    # 按字节截断
    content_bytes = content.encode("utf-8")
    truncated_bytes = content_bytes[:max_chars]
    truncated = truncated_bytes.decode("utf-8", errors="replace")
    return f"{path_line}\n\n```\n{truncated}\n... (content truncated)\n```"


def render_tools_block(tool_defs: list[dict]) -> str:
    """渲染当前可用工具列表（F17）。

    tool_defs 必须是 OpenAI 格式的工具定义列表 [{"type": "function", "function": {...}}, ...]。
    """
    lines = ["## 当前可用工具", ""]
    for tool_def in tool_defs:
        func = tool_def.get("function", {})
        name = func.get("name", "unknown")
        desc = func.get("description", "")
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)


def build_recovery_attachment(
    file_snapshot: list[FileReadRecord],
    tool_defs: list[dict],
) -> str:
    """组装三段恢复内容（F15）：

    1. 最近读过的文件快照（最多 5 个）
    2. 当前可用工具列表
    3. 边界提示消息
    """
    parts: list[str] = []

    # 块 1：文件快照
    if file_snapshot:
        parts.append("## 恢复上下文\n")
        for record in file_snapshot:
            parts.append(render_file_block(record))
            parts.append("")

    # 块 2：工具列表
    if tool_defs:
        parts.append(render_tools_block(tool_defs))
        parts.append("")

    # 块 3：边界提示
    parts.append(BOUNDARY_NOTICE)

    return "\n".join(parts)
