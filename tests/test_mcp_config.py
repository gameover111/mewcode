from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

from mewcode.mcp.config import Config, ServerConfig, load_config


def _make_cfg_file(dirpath: Path, filename: str, data: dict) -> Path:
    p = dirpath / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def test_empty_config():
    with tempfile.TemporaryDirectory() as td:
        cfg = load_config(td)
        assert cfg.servers == {}


def test_project_only():
    with tempfile.TemporaryDirectory() as td:
        _make_cfg_file(Path(td), ".mewcode.yaml", {
            "mcp_servers": {"demo": {"type": "stdio", "command": "python", "args": ["server.py"]}},
        })
        cfg = load_config(td)
        assert "demo" in cfg.servers
        assert cfg.servers["demo"].command == "python"


def test_user_project_merge(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        user_dir = tdp / "userhome"
        user_dir.mkdir()
        (user_dir / ".mewcode").mkdir()
        (user_dir / ".mewcode" / "config.yaml").write_text(yaml.safe_dump({
            "mcp_servers": {
                "shared": {"type": "stdio", "command": "user-cmd", "args": []},
                "unique_to_user": {"type": "http", "url": "https://user.example.com/mcp"},
            },
        }), encoding="utf-8")

        _make_cfg_file(tdp, ".mewcode.yaml", {
            "mcp_servers": {
                "shared": {"type": "stdio", "command": "project-cmd", "args": ["--verbose"]},
                "unique_to_project": {"type": "http", "url": "https://project.example.com/mcp"},
            },
        })

        monkeypatch.setattr("mewcode.mcp.config._user_config_path",
                            lambda: user_dir / ".mewcode" / "config.yaml")

        cfg = load_config(td)
        assert cfg.servers["shared"].command == "project-cmd"
        assert "unique_to_user" in cfg.servers
        assert cfg.servers["unique_to_user"].url == "https://user.example.com/mcp"
        assert "unique_to_project" in cfg.servers


def test_env_var_expansion(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MY_TOKEN", "secret123")
    monkeypatch.setenv("API_KEY", "key456")
    with tempfile.TemporaryDirectory() as td:
        _make_cfg_file(Path(td), ".mewcode.yaml", {
            "mcp_servers": {
                "demo": {
                    "type": "stdio", "command": "npx", "args": ["-y", "server"],
                    "env": {"TOKEN": "${MY_TOKEN}", "API": "${API_KEY}"},
                },
            },
        })
        cfg = load_config(td)
        assert cfg.servers["demo"].env["TOKEN"] == "secret123"
        assert cfg.servers["demo"].env["API"] == "key456"


def test_env_var_no_expand_command():
    with tempfile.TemporaryDirectory() as td:
        _make_cfg_file(Path(td), ".mewcode.yaml", {
            "mcp_servers": {
                "demo": {
                    "type": "stdio", "command": "npx",
                    "args": ["${HOME}/tool"],
                },
            },
        })
        cfg = load_config(td)
        assert cfg.servers["demo"].command == "npx"
        assert cfg.servers["demo"].args == ["${HOME}/tool"]


def test_skip_invalid_type():
    with tempfile.TemporaryDirectory() as td:
        _make_cfg_file(Path(td), ".mewcode.yaml", {
            "mcp_servers": {
                "bad": {"type": "tcp", "command": "x"},
                "good": {"type": "stdio", "command": "y"},
            },
        })
        cfg = load_config(td)
        assert "bad" not in cfg.servers
        assert "good" in cfg.servers


def test_skip_stdio_no_command():
    with tempfile.TemporaryDirectory() as td:
        _make_cfg_file(Path(td), ".mewcode.yaml", {
            "mcp_servers": {
                "incomplete": {"type": "stdio"},
                "complete": {"type": "stdio", "command": "go"},
            },
        })
        cfg = load_config(td)
        assert "incomplete" not in cfg.servers
        assert "complete" in cfg.servers


def test_skip_http_no_url():
    with tempfile.TemporaryDirectory() as td:
        _make_cfg_file(Path(td), ".mewcode.yaml", {
            "mcp_servers": {
                "incomplete": {"type": "http"},
                "complete": {"type": "http", "url": "https://example.com/mcp"},
            },
        })
        cfg = load_config(td)
        assert "incomplete" not in cfg.servers
        assert "complete" in cfg.servers


def test_malformed_yaml():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / ".mewcode.yaml"
        p.write_text("mcp_servers: [not_a_map]\n", encoding="utf-8")
        cfg = load_config(td)
        assert cfg.servers == {}


def test_env_var_undefined_warns():
    with tempfile.TemporaryDirectory() as td:
        _make_cfg_file(Path(td), ".mewcode.yaml", {
            "mcp_servers": {
                "demo": {
                    "type": "stdio", "command": "npx",
                    "env": {"TOKEN": "${UNDEFINED_VAR}"},
                },
            },
        })
        cfg = load_config(td)
        assert cfg.servers["demo"].env["TOKEN"] == ""
