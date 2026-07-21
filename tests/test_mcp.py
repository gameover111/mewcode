from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from mewcode.mcp import (
    McpJsonRpcClient,
    McpServerConfig,
    McpToolAdapter,
    McpToolInfo,
    load_mcp_server_configs,
)
from mewcode.tools.base import ToolContext


def test_load_mcp_server_configs_merges_project_over_user(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MCP_TOKEN", "secret")
    user = tmp_path / "user.yaml"
    project = tmp_path / "mewcode.yaml"
    user.write_text(
        """
mcp:
  servers:
    demo:
      transport: http
      url: https://user.example/mcp
""",
        encoding="utf-8",
    )
    project.write_text(
        """
mcp:
  servers:
    demo:
      transport: http
      url: https://project.example/mcp
      headers:
        Authorization: Bearer ${MCP_TOKEN}
    local:
      command: python
      args: ["server.py"]
""",
        encoding="utf-8",
    )

    configs = load_mcp_server_configs(tmp_path, project, user_config_path=user)

    by_name = {config.name: config for config in configs}
    assert by_name["demo"].url == "https://project.example/mcp"
    assert by_name["demo"].headers["Authorization"] == "Bearer secret"
    assert by_name["local"].transport == "stdio"


def test_http_client_initialize_list_and_call_tool():
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        requests.append(payload)
        if payload.get("method") == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {}}
        elif payload.get("method") == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo text",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                        },
                    }
                ]
            }
        elif payload.get("method") == "tools/call":
            result = {"content": [{"type": "text", "text": payload["params"]["arguments"]["text"]}]}
        else:
            return httpx.Response(202, json={})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": result})

    client = McpJsonRpcClient(
        McpServerConfig(name="remote", transport="http", url="https://example.com/mcp")
    )
    client._http = httpx.Client(transport=httpx.MockTransport(handler))

    tools = client.list_tools()
    result = client.call_tool("echo", {"text": "hello"})

    assert tools[0].name == "echo"
    assert result["content"][0]["text"] == "hello"
    assert [item.get("method") for item in requests][:3] == [
        "initialize",
        "notifications/initialized",
        "tools/list",
    ]


def test_stdio_client_initialize_list_and_call_tool(tmp_path: Path):
    server = tmp_path / "fake_mcp_server.py"
    server.write_text(
        r'''
import json
import sys

for line in sys.stdin:
    msg = json.loads(line)
    method = msg.get("method")
    if method == "initialize":
        print(json.dumps({"jsonrpc":"2.0","id":msg["id"],"result":{"protocolVersion":"2025-06-18","capabilities":{}}}), flush=True)
    elif method == "notifications/initialized":
        continue
    elif method == "tools/list":
        print(json.dumps({"jsonrpc":"2.0","id":msg["id"],"result":{"tools":[{"name":"echo","description":"Echo","inputSchema":{"type":"object","properties":{"text":{"type":"string"}}}}]}}), flush=True)
    elif method == "tools/call":
        text = msg["params"]["arguments"]["text"]
        print(json.dumps({"jsonrpc":"2.0","id":msg["id"],"result":{"content":[{"type":"text","text":text}]}}), flush=True)
''',
        encoding="utf-8",
    )
    client = McpJsonRpcClient(
        McpServerConfig(
            name="local",
            transport="stdio",
            command=os.sys.executable,
            args=[str(server)],
        )
    )

    tools = client.list_tools()
    result = client.call_tool("echo", {"text": "hi"})
    client.close()

    assert tools[0].name == "echo"
    assert result["content"][0]["text"] == "hi"


def test_mcp_tool_adapter_converts_result():
    class FakeClient:
        def call_tool(self, name, arguments):
            return {"content": [{"type": "text", "text": arguments["text"]}]}

    adapter = McpToolAdapter(
        FakeClient(),
        "server",
        McpToolInfo(
            name="echo",
            description="Echo",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        ),
    )

    result = adapter.execute({"text": "hello"}, ToolContext(workspace=Path.cwd()))

    assert adapter.name == "mcp_server_echo"
    assert result.ok is True
    assert result.data["text"] == "hello"
