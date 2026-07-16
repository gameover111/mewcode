from __future__ import annotations

import argparse

from mewcode.config import load_provider_config
from mewcode.providers.base import ProviderError
from mewcode.providers.factory import create_provider
from mewcode.tui import run_chat_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mewcode", description="MewCode 终端 AI 助手")
    parser.add_argument(
        "--config",
        default="mewcode.yaml",
        help="YAML 配置文件路径，默认 mewcode.yaml",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_provider_config(args.config)
        provider = create_provider(config)
    except ProviderError as exc:
        print(f"错误：{exc}")
        return 1

    return run_chat_loop(config, provider)
