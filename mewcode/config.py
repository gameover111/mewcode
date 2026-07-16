from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mewcode.providers.base import ProviderConfig, ProviderError


REQUIRED_FIELDS = ("name", "protocol", "model", "base_url", "api_key")
SUPPORTED_PROTOCOLS = ("anthropic", "openai")


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
    )


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
