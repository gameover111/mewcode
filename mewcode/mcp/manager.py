from __future__ import annotations

import asyncio
import os
import sys
import threading
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mewcode.mcp.config import Config, ServerConfig
from mewcode.mcp.tool import McpTool, adapt_tool


connect_timeout: float = 30.0
close_timeout: float = 5.0


@dataclass
class _Session:
    name: str
    session: Any


class Manager:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._stack: AsyncExitStack | None = None
        self._lock: asyncio.Lock | None = None
        self._sessions: list[_Session] = []
        self._tools: list[McpTool] = []

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    def tools(self) -> list[McpTool]:
        return list(self._tools)

    async def start(self, cfg: Config, version: str) -> None:
        await _await_threadsafe(self._start(cfg, version), self._loop)

    async def close(self) -> None:
        try:
            await _await_threadsafe(self._close(), self._loop)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=close_timeout + 1)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _start(self, cfg: Config, version: str) -> None:
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        self._lock = asyncio.Lock()
        tasks = [
            asyncio.create_task(_connect_one(self, name, server, version))
            for name, server in cfg.servers.items()
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tools.sort(key=lambda tool: tool.full_name)

    async def _close(self) -> None:
        if self._stack is None:
            return
        try:
            await asyncio.wait_for(self._stack.aclose(), timeout=close_timeout)
        except asyncio.TimeoutError:
            print(
                f"[mcp] warn: close timeout ({close_timeout}s), some sessions may leak",
                file=sys.stderr,
            )


async def new_manager(cfg: Config, version: str) -> Manager:
    manager = Manager()
    await manager.start(cfg, version)
    return manager


async def _connect_one(manager: Manager, name: str, server: ServerConfig, version: str) -> None:
    try:
        await asyncio.wait_for(_do_connect(manager, name, server, version), timeout=connect_timeout)
    except asyncio.TimeoutError:
        print(
            f"[mcp] warn: connect server {name} timeout after {connect_timeout}s",
            file=sys.stderr,
        )
    except Exception as exc:
        print(f"[mcp] warn: connect server {name} failed: {exc}", file=sys.stderr)


async def _do_connect(manager: Manager, name: str, server: ServerConfig, version: str) -> None:
    if manager._stack is None or manager._lock is None:
        raise RuntimeError("MCP manager has not been started")

    read, write = await _enter_transport(manager._stack, server)

    from mcp import ClientSession
    import mcp.types as mtypes

    session = await manager._stack.enter_async_context(
        ClientSession(
            read,
            write,
            client_info=mtypes.Implementation(name="mewcode", version=version),
        )
    )
    await session.initialize()
    listed = await session.list_tools()
    tools: list[McpTool] = []
    for tool in getattr(listed, "tools", []) or []:
        adapted = adapt_tool(name, tool, session, manager.loop)
        if adapted is not None:
            tools.append(adapted)

    async with manager._lock:
        manager._sessions.append(_Session(name=name, session=session))
        manager._tools.extend(tools)


async def _enter_transport(stack: AsyncExitStack, server: ServerConfig) -> tuple[Any, Any]:
    if server.type == "stdio":
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=server.command,
            args=server.args,
            env={**os.environ, **server.env},
        )
        transport = await stack.enter_async_context(stdio_client(params))
    else:
        from mcp.client.streamable_http import streamablehttp_client

        transport = await stack.enter_async_context(
            streamablehttp_client(server.url, headers=server.headers or None)
        )

    if not isinstance(transport, tuple) or len(transport) < 2:
        raise RuntimeError("MCP transport did not return read/write streams")
    return transport[0], transport[1]


async def _await_threadsafe(coro, loop: asyncio.AbstractEventLoop) -> Any:
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return await asyncio.wrap_future(future)
