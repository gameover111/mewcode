from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from mewcode.agent import AgentOptions
from mewcode.compact import SessionRuntime, new_session_context
from mewcode.config import effective_context_window, load_provider_config
from mewcode.mcp import load_config as load_mcp_config
from mewcode.mcp import new_manager
from mewcode.providers.base import ProviderError
from mewcode.providers.factory import create_provider
from mewcode.tui import run_chat_loop
from mewcode.tools.registry import create_default_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mewcode", description="MewCode 终端 AI 助手")
    parser.add_argument(
        "--config",
        default="mewcode.yaml",
        help="YAML 配置文件路径，默认 mewcode.yaml",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=8,
        help="Agent Loop 最大轮数，默认 8",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="plan-only 模式：只允许读类工具，输出计划供用户审批",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="整体超时秒数，不设置则无限制",
    )
    parser.add_argument(
        "--permission-mode",
        choices=["default", "acceptEdits", "plan", "bypassPermissions"],
        default=None,
        help="权限模式：default、acceptEdits、plan、bypassPermissions",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_provider_config(args.config)
        provider = create_provider(config)
    except ProviderError as exc:
        print(f"错误：{exc}")
        return 1

    options = AgentOptions(
        max_rounds=args.max_rounds,
        plan_only=args.plan_only,
        permission_mode=args.permission_mode,
        overall_timeout_seconds=args.timeout,
    )

    workspace = Path.cwd()
    registry = create_default_registry()

    # ch8：创建跨轮复用的 SessionRuntime
    session_ctx = new_session_context(str(workspace))
    runtime = SessionRuntime(
        session=session_ctx,
        context_window=effective_context_window(config),
    )

    manager = asyncio.run(new_manager(load_mcp_config(str(workspace)), version="0.1.0"))
    try:
        registered = 0
        for tool in manager.tools():
            try:
                registry.register(tool)
                registered += 1
            except Exception as exc:
                print(f"[mcp] warn: register tool {tool.name} failed: {exc}", file=sys.stderr)
        if registered:
            print(f"已注册 MCP 工具：{registered} 个")

        return run_chat_loop(config, provider, registry=registry, workspace=workspace, options=options, runtime=runtime)
    finally:
        asyncio.run(manager.close())


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
