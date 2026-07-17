from __future__ import annotations

from pathlib import Path

import pytest

from mewcode.tools.base import ToolError
from mewcode.tools.security import ensure_not_private, resolve_workspace_path, truncate_text


def test_resolve_workspace_path_allows_inside_path(tmp_path: Path):
    resolved = resolve_workspace_path(tmp_path, "a/b.txt")

    assert resolved == (tmp_path / "a" / "b.txt").resolve()


def test_resolve_workspace_path_rejects_parent_escape(tmp_path: Path):
    with pytest.raises(ToolError, match="工作区外"):
        resolve_workspace_path(tmp_path, "../secret.txt")


def test_resolve_workspace_path_rejects_absolute_escape(tmp_path: Path):
    outside = tmp_path.parent / "secret.txt"

    with pytest.raises(ToolError, match="工作区外"):
        resolve_workspace_path(tmp_path, str(outside))


def test_ensure_not_private_rejects_env(tmp_path: Path):
    with pytest.raises(ToolError, match="隐私文件"):
        ensure_not_private(tmp_path / ".env")


def test_truncate_text_marks_truncated():
    text, truncated = truncate_text("abcdef", 3)

    assert text == "abc"
    assert truncated is True


def test_truncate_text_keeps_short_text():
    text, truncated = truncate_text("abc", 3)

    assert text == "abc"
    assert truncated is False
