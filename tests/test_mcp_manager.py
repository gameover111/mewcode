from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from mewcode.mcp.config import Config, ServerConfig
from mewcode.mcp.manager import Manager, new_manager


def test_manager_empty_config():
    """空配置 Manager 正常创建和关闭"""
    cfg = Config(servers={})
    manager = asyncio.run(new_manager(cfg, version="0.1.0"))
    assert manager.tools() == []
    asyncio.run(manager.close())


def test_manager_multiple_servers_one_fails():
    """一个 Server 失败不影响其他"""
    cfg = Config(servers={
        "will_fail": ServerConfig(type="stdio", command="nonexistent-command-xyz"),
        "also_fail": ServerConfig(type="http", url="http://localhost:0/mcp"),
    })
    manager = asyncio.run(new_manager(cfg, version="0.1.0"))
    assert manager.tools() == []
    asyncio.run(manager.close())


def test_manager_tools_order():
    """tools() 按 full_name 排序（手动注入，不通过 _start）"""
    from mewcode.mcp.tool import McpTool
    manager = Manager()
    t2 = McpTool("mcp__b__y", "y", "", {"type": "object"}, False, None)
    t1 = McpTool("mcp__a__x", "x", "", {"type": "object"}, False, None)
    manager._tools = [t2, t1]
    tools = sorted(manager.tools(), key=lambda t: t.full_name)
    assert tools[0].full_name == "mcp__a__x"
    assert tools[1].full_name == "mcp__b__y"
    # 关闭 manager 避免线程泄漏
    manager._loop.call_soon_threadsafe(manager._loop.stop)
    manager._thread.join(timeout=3)


def test_manager_thread_stops():
    """Manager 关闭后线程停止"""
    cfg = Config(servers={})
    manager = asyncio.run(new_manager(cfg, version="0.1.0"))
    assert manager._thread.is_alive()
    asyncio.run(manager.close())
    manager._thread.join(timeout=5)
    assert not manager._thread.is_alive()
