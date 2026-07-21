from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mewcode.providers.base import ProviderConfig, ProviderError


REQUIRED_FIELDS = ("name", "protocol", "model", "base_url", "api_key")
SUPPORTED_PROTOCOLS = ("anthropic", "openai")

# F31：协议默认上下文窗口
_DEFAULT_CONTEXT_WINDOWS: dict[str, int] = {
    "anthropic": 200_000,
    "openai": 128_000,
}


def effective_context_window(config: ProviderConfig) -> int:
    """返回 provider 的有效上下文窗口大小（F31）。

    如果配置了 context_window（非零），使用配置值；
    否则按协议返回默认值。
    """
    if config.context_window > 0:
        return config.context_window
    return _DEFAULT_CONTEXT_WINDOWS.get(config.protocol, 128_000)


def load_provider_config(path: str | Path) -> ProviderConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ProviderError(f"配置文件不存在：{config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProviderError(f"配置文件 YAML 格式错误：{exc}") from exc
    except OSError as exc:
        raise ProviderError(f"读取配置文件失败：{exc}") from exc

    if not isinstance(raw, dict):
        raise ProviderError("配置文件必须是 YAML 对象。")

    missing = [field for field in REQUIRED_FIELDS if not raw.get(field)]
    if missing:
        raise ProviderError(f"配置缺少必填字段：{', '.join(missing)}")

    protocol = str(raw["protocol"])
    if protocol not in SUPPORTED_PROTOCOLS:
        supported = ", ".join(SUPPORTED_PROTOCOLS)
        raise ProviderError(f"不支持的协议：{protocol}，支持的协议：{supported}")

    return ProviderConfig(
        name=str(raw["name"]),
        protocol=protocol,  # type: ignore[arg-type]
        model=str(raw["model"]),
        base_url=str(raw["base_url"]),
        api_key=str(raw["api_key"]),
        thinking=_to_bool(raw.get("thinking", False)),
        context_window=int(raw.get("context_window", 0) or 0),
    )


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
