from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


@dataclass(frozen=True)
class ServerConfig:
    type: Literal["stdio", "http"]
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Config:
    servers: dict[str, ServerConfig] = field(default_factory=dict)


@dataclass
class _RawServer:
    type: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)


_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def load_config(root: str) -> Config:
    user_servers = _load_file(_user_config_path())
    project_servers = _load_file(Path(root) / ".mewcode.yaml")

    for servers in (user_servers, project_servers):
        for name, server in servers.items():
            _apply_expansion(name, server)

    merged = _merge_servers(user_servers, project_servers)
    valid: dict[str, ServerConfig] = {}
    for name, server in merged.items():
        config = _validate_server(name, server)
        if config is not None:
            valid[name] = config
    return Config(servers=valid)


def _user_config_path() -> Path:
    try:
        return Path.home() / ".mewcode" / "config.yaml"
    except Exception:
        return Path(".mewcode") / "config.yaml"


def _load_file(path: Path) -> dict[str, _RawServer]:
    try:
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"[mcp] warn: load {path} failed: {exc}", file=sys.stderr)
        return {}

    if not isinstance(data, dict):
        print(f"[mcp] warn: load {path} failed: root must be object", file=sys.stderr)
        return {}

    raw_servers = data.get("mcp_servers") or {}
    if not isinstance(raw_servers, dict):
        print(f"[mcp] warn: load {path} failed: mcp_servers must be object", file=sys.stderr)
        return {}

    servers: dict[str, _RawServer] = {}
    for name, raw in raw_servers.items():
        if isinstance(raw, dict):
            servers[str(name)] = _raw_server(raw)
        else:
            print(f"[mcp] warn: skip server {name}: definition must be object", file=sys.stderr)
    return servers


def _raw_server(raw: dict[str, Any]) -> _RawServer:
    return _RawServer(
        type=str(raw.get("type") or ""),
        command=str(raw.get("command") or ""),
        args=[str(item) for item in raw.get("args") or []] if isinstance(raw.get("args") or [], list) else [],
        env=_string_map(raw.get("env") or {}),
        url=str(raw.get("url") or ""),
        headers=_string_map(raw.get("headers") or {}),
    )


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _expand_vars(value: str) -> tuple[str, list[str]]:
    undefined: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in os.environ:
            undefined.append(name)
            return ""
        return os.environ[name]

    return _VAR_RE.sub(replace, value), undefined


def _apply_expansion(name: str, server: _RawServer) -> None:
    warned: set[str] = set()
    for mapping in (server.env, server.headers):
        for key, value in list(mapping.items()):
            expanded, undefined = _expand_vars(value)
            mapping[key] = expanded
            for var in undefined:
                if var in warned:
                    continue
                warned.add(var)
                print(
                    f"[mcp] warn: undefined env var ${{{var}}} referenced by server {name}",
                    file=sys.stderr,
                )


def _merge_servers(
    user: dict[str, _RawServer],
    project: dict[str, _RawServer],
) -> dict[str, _RawServer]:
    merged = dict(user)
    merged.update(project)
    return merged


def _validate_server(name: str, server: _RawServer) -> ServerConfig | None:
    if server.type not in {"stdio", "http"}:
        print(f"[mcp] warn: skip server {name}: type must be stdio or http", file=sys.stderr)
        return None
    if server.type == "stdio" and not server.command:
        print(f"[mcp] warn: skip server {name}: stdio server requires command", file=sys.stderr)
        return None
    if server.type == "http" and not server.url:
        print(f"[mcp] warn: skip server {name}: http server requires url", file=sys.stderr)
        return None
    if server.type == "stdio":
        return ServerConfig(type="stdio", command=server.command, args=server.args, env=server.env)
    return ServerConfig(type="http", url=server.url, headers=server.headers)
