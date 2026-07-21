# -*- coding: utf-8 -*-
"""ch8 上下文管理 —— Token 估算（F13 / F14）"""
from __future__ import annotations

from mewcode.compact.const import ESTIMATE_CHARS_PER_TOKEN


def estimate_tokens(messages: list, anchor: int = 0, anchor_msg_len: int = 0) -> int:
    """估算消息列表的 token 数。

    锚定模式：已知前 anchor_msg_len 条的精确 token 数为 anchor，
    对其后新增消息做增量字符估算。

    无锚点模式：对整个消息列表做全量字符估算。
    """
    if anchor > 0 and anchor_msg_len > 0 and len(messages) > anchor_msg_len:
        # 增量估算：仅估算 anchor_msg_len 之后新增的消息
        new_messages = messages[anchor_msg_len:]
        delta_chars = _messages_chars(new_messages)
        return anchor + int(delta_chars / ESTIMATE_CHARS_PER_TOKEN)

    # 全量估算
    total_chars = _messages_chars(messages)
    return max(1, int(total_chars / ESTIMATE_CHARS_PER_TOKEN))


def _messages_chars(messages: list) -> int:
    """遍历消息列表，累计 content 的 UTF-8 字节数。"""
    total = 0
    for msg in messages:
        content = getattr(msg, "content", None)
        if content is None:
            continue
        if isinstance(content, str):
            total += len(content.encode("utf-8"))
        elif isinstance(content, list):
            # OpenAI 格式：content 可能是 [{"type": "text", "text": "..."}, ...]
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    total += len(block.get("text", "").encode("utf-8"))
    return total


def calc_usage_anchor(usage: dict | None) -> int:
    """从 provider 返回的 usage 对象计算锚点 token 数（F13）。

    Anthropic: input_tokens + output_tokens + cache_read_input_tokens + cache_creation_input_tokens
    OpenAI:   prompt_tokens + completion_tokens
    """
    if usage is None:
        return 0
    if "input_tokens" in usage:
        return (
            usage.get("input_tokens", 0)
            + usage.get("output_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
        )
    # OpenAI 兼容格式
    return usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
