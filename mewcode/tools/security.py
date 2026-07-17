from __future__ import annotations

from pathlib import Path

from mewcode.tools.base import ToolError


PRIVATE_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
}


def resolve_workspace_path(workspace: Path, user_path: str) -> Path:
    if not user_path or not str(user_path).strip():
        raise ToolError("路径不能为空。")

    workspace_root = workspace.resolve()
    candidate = Path(user_path)
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    resolved = candidate.resolve()

    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ToolError(f"拒绝访问工作区外路径：{user_path}") from exc

    return resolved


def ensure_not_private(path: Path) -> None:
    if path.name in PRIVATE_FILENAMES:
        raise ToolError(f"拒绝访问隐私文件：{path.name}")


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars < 0:
        max_chars = 0
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True
