from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml

from mewcode.tools.base import ToolContext, ToolError, ToolResult
from mewcode.tools.registry import ToolRegistry


MCP_PROTOCOL_VERSION = "2025-06-18"
McpTransport = Literal["stdio", "http"]


class McpError(Exception):
    """MCP 客户端错误，会降级为工具错误或启动警告。"""


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    transport: McpTransport
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class McpToolInfo:
    name: str
    description: str
    input_schema: dict[str, Any]


class McpJsonRpcClient:
    def __init__(self, config: McpServerConfig) -> None:
        self.config = config
        self._next_id = 1
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._http = httpx.Client(timeout=60)
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        result = self.request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "MewCode", "version": "0.1.0"},
            },
        )
        if not isinstance(result, dict):
            raise McpError(f"MCP Server {self.config.name} 初始化响应无效")
        self.notify("notifications/initialized", {})
        self._initialized = True

    def list_tools(self) -> list[McpToolInfo]:
        self.initialize()
        result = self.request("tools/list", {})
        if not isinstance(result, dict):
            raise McpError(f"MCP Server {self.config.name} tools/list 响应无效")
        tools = result.get("tools") or []
        if not isinstance(tools, list):
            raise McpError(f"MCP Server {self.config.name} tools 字段不是数组")
        return [_tool_info(item) for item in tools if isinstance(item, dict)]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.initialize()
        result = self.request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        if not isinstance(result, dict):
            raise McpError(f"MCP Server {self.config.name} tools/call 响应无效")
        return result

    def request(self, method: str, params: dict[str, Any]) -> Any:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
            response = self._send_request(payload, request_id)
            if "error" in response:
                raise McpError(f"MCP {method} 失败：{response['error']}")
            return response.get("result")

    def notify(self, method: str, params: dict[str, Any]) -> None:
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        self._send_notification(payload)

    def close(self) -> None:
        if self._process is not None:
            self._process.terminate()
            self._process = None
        self._http.close()

    def _send_request(self, payload: dict[str, Any], request_id: int) -> dict[str, Any]:
        if self.config.transport == "stdio":
            return self._stdio_request(payload, request_id)
        return self._http_request(payload, request_id)

    def _send_notification(self, payload: dict[str, Any]) -> None:
        if self.config.transport == "stdio":
            process = self._ensure_process()
            assert process.stdin is not None
            process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            process.stdin.flush()
            return
        self._http.post(self.config.url, headers=self.config.headers, json=payload)

    def _stdio_request(self, payload: dict[str, Any], request_id: int) -> dict[str, Any]:
        process = self._ensure_process()
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        process.stdin.flush()

        while True:
            line = process.stdout.readline()
            if line == "":
                raise McpError(f"MCP Server {self.config.name} stdio 已关闭")
            message = json.loads(line)
            if message.get("id") == request_id:
                return message

    def _http_request(self, payload: dict[str, Any], request_id: int) -> dict[str, Any]:
        response = self._http.post(
            self.config.url,
            headers={**self.config.headers, "accept": "application/json, text/event-stream"},
            json=payload,
        )
        response.raise_for_status()
        return _decode_http_rpc_response(response, request_id)

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._process is not None:
            return self._process
        if not self.config.command:
            raise McpError(f"MCP Server {self.config.name} 缺少 command")
        env = os.environ.copy()
        env.update(self.config.env)
        self._process = subprocess.Popen(
            [self.config.command, *self.config.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        return self._process


class McpToolAdapter:
    def __init__(self, client: McpJsonRpcClient, server_name: str, tool: McpToolInfo) -> None:
        self._client = client
        self._remote_name = tool.name
        self.name = f"mcp_{_safe_name(server_name)}_{_safe_name(tool.name)}"
        self.description = f"[MCP:{server_name}] {tool.description or tool.name}"
        self.parameters_schema = tool.input_schema or {"type": "object", "properties": {}}

    def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            result = self._client.call_tool(self._remote_name, arguments)
        except Exception as exc:
            raise ToolError(f"MCP 工具调用失败：{exc}") from exc
        text = _mcp_result_text(result)
        is_error = bool(result.get("isError"))
        return ToolResult(
            ok=not is_error,
            summary=f"MCP 工具 {self._remote_name} {'执行失败' if is_error else '执行完成'}",
            data={"result": result, "text": text},
            error=text if is_error else None,
        )


def load_mcp_server_configs(
    workspace: Path,
    project_config_path: Path | str = "mewcode.yaml",
    user_config_path: Path | None = None,
) -> list[McpServerConfig]:
    workspace = workspace.resolve()
    user_config_path = user_config_path or (Path.home() / ".mewcode" / "settings.yaml")
    project_path = Path(project_config_path)
    if not project_path.is_absolute():
        project_path = workspace / project_path

    merged: dict[str, dict[str, Any]] = {}
    for path in (user_config_path, project_path):
        for name, raw in _read_mcp_servers(path).items():
            if isinstance(raw, dict):
                merged[name] = raw
    return [_server_config(name, raw) for name, raw in merged.items()]


def register_mcp_tools(registry: ToolRegistry, configs: list[McpServerConfig]) -> list[str]:
    registered: list[str] = []
    for config in configs:
        try:
            client = McpJsonRpcClient(config)
            for tool in client.list_tools():
                adapter = McpToolAdapter(client, config.name, tool)
                registry.register(adapter)
                registered.append(adapter.name)
        except Exception:
            continue
    return registered


def _read_mcp_servers(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    mcp = data.get("mcp") or {}
    if isinstance(mcp, dict) and isinstance(mcp.get("servers"), dict):
        return mcp["servers"]
    servers = data.get("mcp_servers")
    if isinstance(servers, dict):
        return servers
    return {}


def _server_config(name: str, raw: dict[str, Any]) -> McpServerConfig:
    transport = str(raw.get("transport") or raw.get("type") or "stdio").lower()
    if transport in {"streamable_http", "streamable-http", "http"}:
        return McpServerConfig(
            name=name,
            transport="http",
            url=_expand_env(str(raw.get("url") or "")),
            headers=_expand_mapping(raw.get("headers") or {}),
        )
    return McpServerConfig(
        name=name,
        transport="stdio",
        command=_expand_env(str(raw.get("command") or "")),
        args=[_expand_env(str(item)) for item in raw.get("args") or []],
        env=_expand_mapping(raw.get("env") or {}),
    )


def _expand_mapping(raw: dict[str, Any]) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(key): _expand_env(str(value)) for key, value in raw.items()}


def _expand_env(value: str) -> str:
    return re.sub(r"\$\{([^}]+)\}", lambda m: os.environ.get(m.group(1), ""), value)


def _tool_info(raw: dict[str, Any]) -> McpToolInfo:
    return McpToolInfo(
        name=str(raw.get("name") or ""),
        description=str(raw.get("description") or ""),
        input_schema=raw.get("inputSchema") if isinstance(raw.get("inputSchema"), dict) else {},
    )


def _decode_http_rpc_response(response: httpx.Response, request_id: int) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if not data or data == "[DONE]":
                continue
            message = json.loads(data)
            if message.get("id") == request_id:
                return message
        raise McpError(f"HTTP MCP 响应中没有 id={request_id} 的回包")
    message = response.json()
    if isinstance(message, list):
        for item in message:
            if isinstance(item, dict) and item.get("id") == request_id:
                return item
        raise McpError(f"HTTP MCP 批量响应中没有 id={request_id} 的回包")
    if isinstance(message, dict):
        return message
    raise McpError("HTTP MCP 响应不是 JSON-RPC 对象")


def _mcp_result_text(result: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in result.get("content") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return "\n".join(parts)


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return safe or "tool"
