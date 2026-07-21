# -*- coding: utf-8 -*-
"""ch8 上下文管理 —— 编排入口 + 对外类型"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

from mewcode.compact.const import AUTO_SAFETY_MARGIN, MANUAL_SAFETY_MARGIN, SUMMARY_RESERVE
from mewcode.compact.layer1 import offload_and_snip
from mewcode.compact.layer2 import auto_compact as _auto_compact
from mewcode.compact.layer2 import force_compact as _force_compact
from mewcode.compact.state import SessionRuntime
from mewcode.compact.token import estimate_tokens


class TriggerKind(enum.Enum):
    AUTO = "auto"
    MANUAL = "manual"
    EMERGENCY = "emergency"


@dataclass
class CompressionResult:
    """manage_context 的返回值"""
    triggered: bool = False
    layer1_applied: bool = False
    layer2_applied: bool = False
    estimated_tokens: int = 0
    breaker_tripped: bool = False


def manage_context(
    conversation,
    runtime: SessionRuntime,
    provider=None,
    config=None,
    tool_defs: list[dict] | None = None,
    trigger: TriggerKind = TriggerKind.AUTO,
) -> CompressionResult:
    """上下文管理编排入口（F6/F7/F25）。

    Agent 主循环每轮请求组装前调用。

    执行顺序：
    1. 第 1 层：工具结果落盘 + 预览替换（总是执行）
    2. 检查熔断（仅 AUTO 路径）
    3. Token 估算 + 阈值判断
    4. 第 2 层：LLM 摘要（触达阈值时）
    """
    result = CompressionResult()
    tool_defs = tool_defs or []

    # ---- Layer 1 ----
    if runtime.session is not None:
        messages = conversation.snapshot()
        new_messages = offload_and_snip(messages, runtime.session, runtime.replacement)
        if new_messages is not messages:
            conversation.replace_history(new_messages)
            result.layer1_applied = True

    # ---- Check breaker ----
    if trigger == TriggerKind.AUTO and runtime.auto_tracking.tripped:
        result.breaker_tripped = True
        result.estimated_tokens = estimate_tokens(
            conversation.snapshot(), runtime.usage_anchor, runtime.anchor_msg_len
        )
        return result

    # ---- Token estimate ----
    messages = conversation.snapshot()
    estimated = estimate_tokens(messages, runtime.usage_anchor, runtime.anchor_msg_len)
    result.estimated_tokens = estimated

    # Calculate threshold
    if trigger == TriggerKind.MANUAL:
        safety = MANUAL_SAFETY_MARGIN
    elif trigger == TriggerKind.EMERGENCY:
        safety = MANUAL_SAFETY_MARGIN  # 紧急模式也用较小的安全余量
    else:
        safety = AUTO_SAFETY_MARGIN

    threshold = runtime.context_window - SUMMARY_RESERVE - safety

    if trigger == TriggerKind.AUTO and estimated < threshold:
        return result

    # ---- Layer 2 ----
    if provider is None or config is None:
        return result

    if trigger in (TriggerKind.MANUAL, TriggerKind.EMERGENCY):
        _force_compact(conversation, runtime, provider, config, tool_defs)
        result.layer2_applied = True
    else:
        ok = _auto_compact(conversation, runtime, provider, config, tool_defs)
        result.layer2_applied = ok

    return result
