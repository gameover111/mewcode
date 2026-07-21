# -*- coding: utf-8 -*-
"""ch8 上下文管理 —— 第 1 层：工具结果预防性落盘 + 预览替换（F1-F6）"""
from __future__ import annotations

from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Any

from mewcode.compact.const import (
    MESSAGE_AGGREGATE_LIMIT,
    PREVIEW_HEAD_BYTES,
    PREVIEW_HEAD_LINES,
    SINGLE_RESULT_LIMIT,
)
from mewcode.compact.state import ContentReplacementState, SessionContext


def build_preview(content: str, spill_path: str, byte_count: int) -> str:
    """构造四项预览替换体（F4）"""
    lines = content.split("\n")
    head_lines = lines[:PREVIEW_HEAD_LINES]
    head_text = "\n".join(head_lines)
    head_bytes = head_text.encode("utf-8")
    if len(head_bytes) > PREVIEW_HEAD_BYTES:
        # 按字节截断
        truncated = head_bytes[:PREVIEW_HEAD_BYTES]
        # 避免截断在多字节字符中间
        head_text = truncated.decode("utf-8", errors="replace")
    return (
        f"[上下文管理] 工具结果已截断\n"
        f"原始大小：{byte_count:,} 字节\n"
        f"完整内容已保存至：{spill_path}\n"
        f"--- 预览（前 {min(PREVIEW_HEAD_LINES, len(head_lines))} 行 / {min(PREVIEW_HEAD_BYTES, len(head_bytes))} 字节）---\n"
        f"{head_text}\n"
        f"--- 预览结束 ---\n"
        f"如需查看完整内容，请使用 read_file 工具读取：{spill_path}"
    )


def spill_single(session: SessionContext, content: str, tool_use_id: str) -> str | None:
    """将单条工具结果落盘（F3），成功返回路径，失败返回 None。

    文件名使用 tool_use_id，已存在则跳过不重复写。
    """
    spill_dir = Path(session.spill_dir)
    spill_dir.mkdir(parents=True, exist_ok=True)
    file_path = spill_dir / tool_use_id

    if file_path.exists():
        return str(file_path)

    try:
        file_path.write_text(content, encoding="utf-8")
        return str(file_path)
    except OSError:
        return None


def _result_byte_count(tool_result: Any) -> int:
    """返回 tool_result content 的 UTF-8 字节数。"""
    content = getattr(tool_result, "content", None)
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content.encode("utf-8"))
    return 0


def _result_content(tool_result: Any) -> str:
    content = getattr(tool_result, "content", None)
    if content is None:
        return ""
    return str(content)


def offload_and_snip(
    messages: list,
    session: SessionContext,
    replacement: ContentReplacementState,
) -> list:
    """对消息列表中每条 RoleTool 消息做第 1 层预防性压缩（F1/F2/F2a）。

    返回替换后的新消息列表（不修改原列表）。
    如果无任何替换发生，返回原始 messages 列表（身份相同），
    供调用方用 `is` 判断是否真正发生了变化。
    """
    new_messages: list | None = None

    for i, msg in enumerate(messages):
        role = getattr(msg, "role", None)
        if role != "tool":
            if new_messages is not None:
                new_messages.append(msg)
            continue

        tool_use_id = getattr(msg, "tool_call_id", None)
        content = _result_content(msg)

        if tool_use_id is None or not content:
            if new_messages is not None:
                new_messages.append(msg)
            continue

        # F2a：构建候选列表（此消息只有一项，候选列表体现在外层按消息聚合的
        # 第二轮判断；此处先处理单条阈值）
        byte_count = len(content.encode("utf-8"))

        def _decide() -> tuple[str, str | None]:
            if byte_count <= SINGLE_RESULT_LIMIT:
                return ("kept", None)

            spill_path = spill_single(session, content, tool_use_id)
            if spill_path is None:
                return ("skip", None)

            preview = build_preview(content, spill_path, byte_count)
            return ("replaced", preview)

        new_content = replacement.decide_once(tool_use_id, content, _decide)

        if new_content != content:
            # 首次替换：惰性创建 new_messages，拷贝之前所有消息
            if new_messages is None:
                new_messages = list(messages[:i])
            new_msg = dc_replace(msg, content=new_content)
            new_messages.append(new_msg)
        else:
            if new_messages is not None:
                new_messages.append(msg)

    # 没有发生任何替换 → 返回原始列表
    if new_messages is None:
        return messages

    # 第二轮：聚合判断（F2）
    # 收集所有 tool 消息中第一轮未被替换的项（仍持有完整原文），
    # 跳过已替换成预览的消息，按字节排序
    tool_indices: list[tuple[int, str, int]] = []  # (idx, content, byte_count)
    for i, msg in enumerate(new_messages):
        role = getattr(msg, "role", None)
        if role != "tool":
            continue
        content = _result_content(msg)
        if not content:
            continue
        # 只在第一轮未被替换时加入候补列表
        # 注：如果 msg is messages[i]（身份相同），说明第一轮未改动
        if msg is messages[min(i, len(messages) - 1)]:
            tool_indices.append((i, content, len(content.encode("utf-8"))))

    # 计算聚合字节
    aggregate_bytes = sum(bc for _, _, bc in tool_indices)
    if aggregate_bytes <= MESSAGE_AGGREGATE_LIMIT:
        return new_messages

    # 按字节从大到小排序
    tool_indices.sort(key=lambda x: x[2], reverse=True)

    # 从最大的开始落盘，直到剩余聚合字节 ≤ MESSAGE_AGGREGATE_LIMIT
    # 注意：这里绕过 ContentReplacementState.decide_once，
    # 因为第一轮已将这些 tool_use_id 记作 "kept"，第二轮无法重新决定。
    for idx, content, bc in tool_indices:
        if aggregate_bytes <= MESSAGE_AGGREGATE_LIMIT:
            break

        msg = new_messages[idx]
        tool_use_id = getattr(msg, "tool_call_id", None)
        if tool_use_id is None:
            continue

        spill_path = spill_single(session, content, tool_use_id)
        if spill_path is None:
            continue

        preview = build_preview(content, spill_path, bc)
        new_messages[idx] = dc_replace(msg, content=preview)
        aggregate_bytes -= bc

    return new_messages
