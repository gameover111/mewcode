# -*- coding: utf-8 -*-
"""ch8 上下文管理 —— 第 2 层：LLM 摘要 + 编排（F7-F12, F25-F29）"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

from mewcode.compact.const import (
    AUTO_SAFETY_MARGIN,
    ESTIMATE_CHARS_PER_TOKEN,
    MANUAL_SAFETY_MARGIN,
    PTL_DROP_PERCENTAGE,
    PTL_RETRY_LIMIT,
    RECENT_KEEP_MESSAGES,
    RECENT_KEEP_TOKENS,
    SUMMARY_RESERVE,
)
from mewcode.compact.recovery import build_recovery_attachment
from mewcode.compact.state import SessionRuntime
from mewcode.compact.summary_prompt import build_summary_prompt, extract_summary
from mewcode.compact.token import estimate_tokens
from mewcode.providers.base import ChatMessage, ChatRequest, ProviderConfig, ProviderEvent


@dataclass
class _CompactAttempt:
    """单次 compact 尝试的结果"""
    summary_text: str | None = None
    error: str | None = None


def _messages_chars(messages: list) -> int:
    """计算消息列表中 content 的 UTF-8 总字节数。"""
    total = 0
    for msg in messages:
        content = getattr(msg, "content", None)
        if content is None:
            continue
        if isinstance(content, str):
            total += len(content.encode("utf-8"))
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    total += len(block.get("text", "").encode("utf-8"))
    return total


# ---------------------------------------------------------------------------
# pick_recent_tail
# ---------------------------------------------------------------------------

def pick_recent_tail(messages: list) -> tuple[list, list]:
    """从消息列表尾部分割近期原文（F11/F12）。

    返回 (to_summarize, recent)：
      - recent 从尾部倒序累加，满足 token ≥ RECENT_KEEP_TOKENS 且条数 ≥ RECENT_KEEP_MESSAGES
      - 不允许切开 tool_use ↔ tool_result 对
    """
    if not messages:
        return [], []

    recent: list = []
    accumulated_chars = 0
    accumulated_count = 0

    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        role = getattr(msg, "role", None)
        content = getattr(msg, "content", None) or ""
        if isinstance(content, list):
            content = "".join(
                b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
        msg_chars = len(content.encode("utf-8")) if content else 0

        # F12：如果是 tool 消息，确保对应的 assistant（含 tool_use）也被包含
        if role == "tool":
            tool_call_id = getattr(msg, "tool_call_id", None)
            if tool_call_id:
                # 向前查找包含此 tool_call 的 assistant 消息
                j = i - 1
                while j >= 0:
                    prev_msg = messages[j]
                    prev_role = getattr(prev_msg, "role", None)
                    prev_tool_calls = getattr(prev_msg, "tool_calls", None)
                    if prev_role == "assistant" and prev_tool_calls:
                        for tc in prev_tool_calls:
                            if getattr(tc, "id", None) == tool_call_id:
                                # 确保 assistant 消息也被包含
                                if prev_msg not in recent:
                                    recent.insert(0, prev_msg)
                                    prev_content = getattr(prev_msg, "content", None) or ""
                                    if isinstance(prev_content, list):
                                        prev_content = "".join(
                                            b.get("text", "") for b in prev_content
                                            if isinstance(b, dict) and b.get("type") == "text"
                                        )
                                    accumulated_chars += (
                                        len(prev_content.encode("utf-8")) if prev_content else 0
                                    )
                                    accumulated_count += 1
                                break
                    j -= 1

        recent.insert(0, msg)
        accumulated_chars += msg_chars
        accumulated_count += 1

        # 满足阈值即停止
        estimated_tokens = int(accumulated_chars / ESTIMATE_CHARS_PER_TOKEN)
        if estimated_tokens >= RECENT_KEEP_TOKENS and accumulated_count >= RECENT_KEEP_MESSAGES:
            break

    split_point = len(messages) - len(recent)
    to_summarize = list(messages[:split_point])
    return to_summarize, list(recent)


# ---------------------------------------------------------------------------
# group_by_user_turn
# ---------------------------------------------------------------------------

def group_by_user_turn(messages: list) -> list[list]:
    """将消息列表按"用户消息 → 后续 assistant/tool 往返"分组（F27）。

    每组从一条 role=user 的消息开始。
    """
    groups: list[list] = []
    current_group: list = []

    for msg in messages:
        role = getattr(msg, "role", None)
        if role == "user" and current_group:
            groups.append(current_group)
            current_group = []
        current_group.append(msg)

    if current_group:
        groups.append(current_group)

    return groups


# ---------------------------------------------------------------------------
# summarize_once
# ---------------------------------------------------------------------------

def summarize_once(
    provider,
    config: ProviderConfig,
    messages_to_summarize: list,
) -> _CompactAttempt:
    """执行一次 LLM 摘要请求（F8/F9/F10）。

    不传工具定义，禁止工具调用。返回 _CompactAttempt。
    """
    if not messages_to_summarize:
        return _CompactAttempt(summary_text="")

    prompt = build_summary_prompt(messages_to_summarize)
    summary_messages = [ChatMessage(role="user", content=prompt)]

    request = ChatRequest(
        messages=summary_messages,
        config=config,
        tools=[],          # F8：禁止工具
        tool_choice=None,
        system=None,
        reminder="",
    )

    text_parts: list[str] = []

    try:
        for event in provider.stream_chat(request):
            if event.type == "text":
                text_parts.append(event.content)
            elif event.type == "error":
                return _CompactAttempt(error=event.content)
            elif event.type == "done":
                break
    except Exception as exc:
        return _CompactAttempt(error=str(exc))

    raw = "".join(text_parts)
    summary = extract_summary(raw)
    if not summary:
        return _CompactAttempt(error="摘要结果为空")

    return _CompactAttempt(summary_text=summary)


# ---------------------------------------------------------------------------
# ptl_retry
# ---------------------------------------------------------------------------

def _is_prompt_too_long(error_msg: str) -> bool:
    """检测是否为 prompt_too_long 类错误。"""
    keywords = [
        "prompt_too_long",
        "context_length_exceeded",
        "context window",
        "too long",
        "maximum context",
        "reduce the length",
        "token",
        "400",
        "413",
    ]
    error_lower = error_msg.lower()
    return any(kw.lower() in error_lower for kw in keywords)


def ptl_retry(
    provider,
    config: ProviderConfig,
    messages: list,
    max_direct_retries: int = PTL_RETRY_LIMIT,
) -> _CompactAttempt:
    """摘要请求 PTL 自重试（F27）。

    先直接重试最多 max_direct_retries 次（每次丢最旧 1 组），
    还不行则按 PTL_DROP_PERCENTAGE 比例丢弃，直至请求能塞下或耗尽。
    """
    groups = group_by_user_turn(messages)
    if not groups:
        return _CompactAttempt(error="无可用于摘要的消息组")

    retry_count = 0
    drop_count = 1  # 每次丢弃的组数

    for attempt in range(PTL_RETRY_LIMIT + 20):  # +20 给比例丢弃阶段留足次数
        flat_messages = [msg for grp in groups for msg in grp]
        result = summarize_once(provider, config, flat_messages)

        if result.summary_text:
            return result

        # 检查是否是 PTL 错误
        if result.error and not _is_prompt_too_long(result.error):
            return result  # 非 PTL 错误，直接返回

        # Discard oldest groups
        if attempt < PTL_RETRY_LIMIT:
            # 直接重试阶段：每次丢最旧 1 组
            if not groups:
                break
            groups = groups[drop_count:]
        else:
            # 比例丢弃阶段：每次丢 ceil(剩余组数 * PTL_DROP_PERCENTAGE)
            if not groups:
                break
            drop_count = max(1, math.ceil(len(groups) * PTL_DROP_PERCENTAGE))
            groups = groups[drop_count:]

        if not groups:
            break

    return _CompactAttempt(error="PTL 重试耗尽：摘要请求仍无法容纳")


# ---------------------------------------------------------------------------
# run_summary
# ---------------------------------------------------------------------------

def run_summary(
    provider,
    config: ProviderConfig,
    messages_to_summarize: list,
) -> str | None:
    """执行摘要（含 PTL 重试），成功返回摘要文本，失败返回 None。"""
    result = summarize_once(provider, config, messages_to_summarize)
    if result.summary_text:
        return result.summary_text

    if result.error and _is_prompt_too_long(result.error):
        # PTL 重试
        retry_result = ptl_retry(provider, config, messages_to_summarize)
        return retry_result.summary_text

    return None


# ---------------------------------------------------------------------------
# auto_compact / force_compact
# ---------------------------------------------------------------------------

def auto_compact(
    conversation,
    runtime: SessionRuntime,
    provider,
    config: ProviderConfig,
    tool_defs: list[dict],
) -> bool:
    """自动触发摘要（F7）：检查阈值 → 摘要 → 替换历史。

    返回 True 表示摘要成功，False 表示失败（含熔断跳过）。
    """
    messages = conversation.snapshot()

    # 估算当前 token
    estimated = estimate_tokens(messages, runtime.usage_anchor, runtime.anchor_msg_len)
    threshold = runtime.context_window - SUMMARY_RESERVE - AUTO_SAFETY_MARGIN

    if estimated < threshold:
        return False  # 未触发

    return _do_compact(conversation, runtime, provider, config, tool_defs, messages)


def force_compact(
    conversation,
    runtime: SessionRuntime,
    provider,
    config: ProviderConfig,
    tool_defs: list[dict],
) -> tuple[int, int]:
    """手动/紧急触发摘要（F22/F25）：跳过阈值检查，无条件执行。

    返回 (before_tokens, after_tokens)。
    """
    messages = conversation.snapshot()
    before = estimate_tokens(messages, runtime.usage_anchor, runtime.anchor_msg_len)

    success = _do_compact(conversation, runtime, provider, config, tool_defs, messages)
    if not success:
        return before, before

    after = estimate_tokens(conversation.snapshot())
    return before, after


def _do_compact(
    conversation,
    runtime: SessionRuntime,
    provider,
    config: ProviderConfig,
    tool_defs: list[dict],
    messages: list,
) -> bool:
    """执行一次完整的摘要流程并重建对话历史。"""
    # 1. 分割尾部
    to_summarize, recent = pick_recent_tail(messages)

    if not to_summarize:
        return False  # 没有可摘要的内容

    # 2. 执行摘要
    summary = run_summary(provider, config, to_summarize)
    if summary is None:
        runtime.auto_tracking.record_failure()
        return False

    # 3. 构造恢复段
    file_snapshot = runtime.recovery.snapshot()
    recovery_text = build_recovery_attachment(file_snapshot, tool_defs)

    # 4. 组装新消息列表：[摘要] + [恢复段] + [近期原文]
    new_messages: list[ChatMessage] = []
    new_messages.append(ChatMessage(role="user", content=summary))
    new_messages.append(ChatMessage(role="user", content=recovery_text))
    new_messages.extend(recent)

    # 5. 替换对话历史
    conversation.replace_history(new_messages)

    # 6. 重置 token 锚点 + 记录成功
    runtime.usage_anchor = 0
    runtime.anchor_msg_len = 0
    runtime.auto_tracking.record_success()

    return True
