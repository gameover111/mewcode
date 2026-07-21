# -*- coding: utf-8 -*-
"""ch8 上下文管理 —— 会话级状态对象"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from mewcode.compact.const import MAX_CONSECUTIVE_AUTO_COMPACT_FAILURES, RECOVERY_FILE_LIMIT


# ---------------------------------------------------------------------------
# SessionContext
# ---------------------------------------------------------------------------

@dataclass
class SessionContext:
    """会话标识与落盘目录（F32 / F33）"""
    session_id: str
    spill_dir: str


def new_session_context(workspace: str) -> SessionContext:
    session_id = f"{int(time.time())}-{secrets.token_hex(4)}"
    spill_dir = str(Path(workspace) / ".mewcode" / "sessions" / session_id / "tool-results")
    Path(spill_dir).mkdir(parents=True, exist_ok=True)
    return SessionContext(session_id=session_id, spill_dir=spill_dir)


# ---------------------------------------------------------------------------
# ContentReplacementState
# ---------------------------------------------------------------------------

class ContentReplacementState:
    """第 1 层替换账本 —— 决策冻结（F5）

    保证同一个 tool_use_id 的替换决策在会话内只做一次，后续回放
    逐字节一致，保护 prompt cache 前缀。
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._replacements: dict[str, str] = {}

    def decide_once(
        self,
        tool_use_id: str,
        original: str,
        decide: Callable[[], tuple[str, str | None]],
    ) -> str:
        """原子决策：已 seen → 返回缓存结果；未 seen → 调 decide() 后冻结。

        decide() 返回 (kind, preview)：
          - kind == "kept"    → 保留原文，记 seen_ids
          - kind == "replaced" → 替换为 preview 字符串，记 seen_ids + replacements
          - kind == "skip"    → 不做任何记录，下次重新评估
        """
        if tool_use_id in self._seen_ids:
            return self._replacements.get(tool_use_id, original)

        kind, preview = decide()

        if kind == "skip":
            return original

        self._seen_ids.add(tool_use_id)

        if kind == "replaced" and preview is not None:
            self._replacements[tool_use_id] = preview
            return preview

        # kind == "kept"：记 seen_ids 但不记 replacements，返回原文
        return original

    @property
    def seen_ids(self) -> set[str]:
        return set(self._seen_ids)

    @property
    def replacements(self) -> dict[str, str]:
        return dict(self._replacements)


# ---------------------------------------------------------------------------
# CompactCircuitBreaker
# ---------------------------------------------------------------------------

class CompactCircuitBreaker:
    """自动摘要熔断器（F28 / F29）

    连续失败达到 MAX_CONSECUTIVE_AUTO_COMPACT_FAILURES 后跳闸，
    跳闸后自动路径不再触发摘要，手动/紧急仍可绕过。
    """

    def __init__(self) -> None:
        self._consecutive_failures: int = 0

    def record_success(self) -> None:
        self._consecutive_failures = 0

    def record_failure(self) -> None:
        self._consecutive_failures += 1

    @property
    def tripped(self) -> bool:
        return self._consecutive_failures >= MAX_CONSECUTIVE_AUTO_COMPACT_FAILURES


# ---------------------------------------------------------------------------
# RecoveryState
# ---------------------------------------------------------------------------

@dataclass
class FileReadRecord:
    path: str
    content: str  # 纯净字节（原始内容，不带行号前缀）
    timestamp: datetime


class RecoveryState:
    """最近读取文件追踪（F19 / F20）—— 线程安全"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._files: dict[str, FileReadRecord] = {}

    def record_file(self, path: str, content: str) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._files[path] = FileReadRecord(path=path, content=content, timestamp=now)

    def snapshot(self) -> list[FileReadRecord]:
        """返回按时间倒序排列的快照副本，最多 RECOVERY_FILE_LIMIT 条"""
        with self._lock:
            records = sorted(
                self._files.values(),
                key=lambda r: r.timestamp,
                reverse=True,
            )
            return [FileReadRecord(r.path, r.content, r.timestamp) for r in records[:RECOVERY_FILE_LIMIT]]


# ---------------------------------------------------------------------------
# SessionRuntime
# ---------------------------------------------------------------------------

@dataclass
class SessionRuntime:
    """跨 Agent.run 轮次持有的长生命周期状态容器。

    TUI Model 持有同一份 SessionRuntime 跨轮复用。
    """
    replacement: ContentReplacementState = field(default_factory=ContentReplacementState)
    recovery: RecoveryState = field(default_factory=RecoveryState)
    auto_tracking: CompactCircuitBreaker = field(default_factory=CompactCircuitBreaker)
    session: SessionContext | None = None
    context_window: int = 200_000
    usage_anchor: int = 0
    anchor_msg_len: int = 0
    _run_lock: threading.Lock = field(default_factory=threading.Lock)
