from __future__ import annotations

import datetime
import os
import platform
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class Environment:
    working_dir: str = ""
    platform_str: str = ""
    date: str = ""
    git_status: str = ""
    version: str = ""
    model: str = ""

    def render(self) -> str:
        parts = [f"工作目录：{self.working_dir}"]
        if self.platform_str:
            parts.append(f"平台：{self.platform_str}")
        if self.date:
            parts.append(f"日期：{self.date}")
        if self.git_status:
            parts.append(f"git：{self.git_status}")
        if self.version:
            parts.append(f"版本：{self.version}")
        if self.model:
            parts.append(f"模型：{self.model}")
        return "环境信息 | " + " | ".join(parts)


def _get_git_status(timeout: float = 2.0) -> str:
    """采集 git 状态，失败/非 git 目录降级为空。"""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return ""
        lines = result.stdout.strip().split("\n")
        if not lines or lines == [""]:
            return "clean"
        return f"{len(lines)} change(s)"
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError, OSError):
        return ""


def gather_environment(version: str = "", model: str = "") -> Environment:
    """采集运行环境信息，失败项降级留空。"""
    cwd = ""
    try:
        cwd = os.getcwd()
    except OSError:
        pass

    return Environment(
        working_dir=cwd,
        platform_str=platform.system().lower() if hasattr(platform, "system") else sys.platform,
        date=datetime.date.today().isoformat(),
        git_status=_get_git_status(),
        version=version,
        model=model,
    )
