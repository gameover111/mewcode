# -*- coding: utf-8 -*-
"""ch8 上下文管理 —— 对外公开接口"""
from mewcode.compact.compact import CompressionResult, TriggerKind, manage_context
from mewcode.compact.const import (
    AUTO_SAFETY_MARGIN,
    ESTIMATE_CHARS_PER_TOKEN,
    MANUAL_SAFETY_MARGIN,
    MAX_CONSECUTIVE_AUTO_COMPACT_FAILURES,
    MESSAGE_AGGREGATE_LIMIT,
    PREVIEW_HEAD_BYTES,
    PREVIEW_HEAD_LINES,
    PTL_DROP_PERCENTAGE,
    PTL_RETRY_LIMIT,
    RECENT_KEEP_MESSAGES,
    RECENT_KEEP_TOKENS,
    RECOVERY_FILE_LIMIT,
    RECOVERY_TOKENS_PER_FILE,
    SINGLE_RESULT_LIMIT,
    SUMMARY_RESERVE,
)
from mewcode.compact.layer2 import force_compact as run_force_compact
from mewcode.compact.state import (
    ContentReplacementState,
    FileReadRecord,
    RecoveryState,
    SessionContext,
    SessionRuntime,
    new_session_context,
)
from mewcode.compact.token import calc_usage_anchor, estimate_tokens

__all__ = [
    # compact orchestration
    "manage_context",
    "TriggerKind",
    "CompressionResult",
    "run_force_compact",
    # state
    "SessionRuntime",
    "SessionContext",
    "new_session_context",
    "ContentReplacementState",
    "RecoveryState",
    "FileReadRecord",
    # token
    "estimate_tokens",
    "calc_usage_anchor",
    # constants
    "SINGLE_RESULT_LIMIT",
    "MESSAGE_AGGREGATE_LIMIT",
    "SUMMARY_RESERVE",
    "AUTO_SAFETY_MARGIN",
    "MANUAL_SAFETY_MARGIN",
    "RECOVERY_FILE_LIMIT",
    "RECOVERY_TOKENS_PER_FILE",
    "RECENT_KEEP_TOKENS",
    "RECENT_KEEP_MESSAGES",
    "MAX_CONSECUTIVE_AUTO_COMPACT_FAILURES",
    "PTL_RETRY_LIMIT",
    "PTL_DROP_PERCENTAGE",
    "ESTIMATE_CHARS_PER_TOKEN",
    "PREVIEW_HEAD_BYTES",
    "PREVIEW_HEAD_LINES",
]
