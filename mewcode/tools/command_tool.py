from __future__ import annotations

import subprocess
from typing import Any

from mewcode.tools.base import ToolContext, ToolError, ToolResult
from mewcode.tools.security import resolve_workspace_path, truncate_text


class RunCommandTool:
    name = "run_command"
    description = "在工作区内执行一次命令，返回退出码、标准输出和标准错误。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的命令。"},
            "cwd": {"type": "string", "description": "工作目录，必须位于工作区内。"},
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        command = arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ToolError("参数 command 必须是非空字符串。")
        cwd_arg = arguments.get("cwd")
        if cwd_arg is None:
            cwd = context.workspace.resolve()
        elif isinstance(cwd_arg, str):
            cwd = resolve_workspace_path(context.workspace, cwd_arg)
        else:
            raise ToolError("参数 cwd 必须是字符串。")
        if not cwd.exists() or not cwd.is_dir():
            raise ToolError(f"工作目录不存在或不是目录：{cwd_arg}")

        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=context.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            stdout, stdout_truncated = truncate_text(stdout, context.max_output_chars)
            stderr, stderr_truncated = truncate_text(stderr, context.max_output_chars)
            return ToolResult(
                ok=False,
                summary=f"命令超时：{command}",
                data={
                    "exit_code": None,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                    "timeout_seconds": context.timeout_seconds,
                },
                error=f"命令执行超过 {context.timeout_seconds} 秒。",
            )

        stdout, stdout_truncated = truncate_text(completed.stdout, context.max_output_chars)
        stderr, stderr_truncated = truncate_text(completed.stderr, context.max_output_chars)
        ok = completed.returncode == 0
        return ToolResult(
            ok=ok,
            summary=f"命令执行完成，退出码：{completed.returncode}",
            data={
                "exit_code": completed.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
            },
            error=None if ok else f"命令退出码非 0：{completed.returncode}",
        )
