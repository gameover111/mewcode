# MewCode ch7 MCP 客户端 Plan

## 架构

新增 `mewcode/mcp.py`，包含配置加载、JSON-RPC 客户端、MCP 工具适配器和注册函数。

启动链路：

1. `cli.py` 加载 LLM Provider 配置。
2. 创建内置 `ToolRegistry`。
3. `load_mcp_server_configs()` 读取用户级和项目级 MCP 配置。
4. `register_mcp_tools()` 逐个连接 Server，初始化并列出工具。
5. 每个 MCP 工具包装为 `McpToolAdapter` 注册进工具中心。
6. TUI/Agent 使用同一个 registry，调用时无感。

## 模块设计

### `McpServerConfig`

字段：
- `name`
- `transport`: `stdio` 或 `http`
- stdio: `command`、`args`、`env`
- http: `url`、`headers`

### `McpJsonRpcClient`

职责：
- 维护自增 JSON-RPC id。
- stdio 模式下管理子进程生命周期。
- HTTP 模式下用 `httpx.Client.post()` 发送 JSON-RPC。
- `initialize()` 完成握手。
- `list_tools()` 调用 `tools/list`。
- `call_tool()` 调用 `tools/call`。

### `McpToolAdapter`

把远端 MCP 工具包装为 MewCode `Tool`：
- `name = mcp_<server>_<tool>`
- `description` 保留 Server 来源。
- `parameters_schema` 来自 MCP `inputSchema`。
- `execute()` 内部调用 `tools/call` 并转换为 `ToolResult`。

## JSON-RPC 流程

初始化：

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"MewCode","version":"0.1.0"}}}
```

初始化完成通知：

```json
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
```

列工具：

```json
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

调用工具：

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"tool_name","arguments":{}}}
```

## 配置合并

加载顺序：

1. 用户级：`~/.mewcode/settings.yaml`
2. 项目级：`mewcode.yaml`

同名 Server 后加载覆盖先加载，即项目级覆盖用户级。

## 失败处理

- 配置文件不存在：视为空配置。
- 配置格式非法：跳过。
- 单个 Server 连接失败：跳过该 Server。
- 单个工具调用失败：返回 `ToolResult(ok=False)`。

## 当前取舍

MewCode 当前 Agent/TUI 是同步架构，因此 ch7 MCP 客户端先用同步 I/O 实现。请求 id 配对和连接生命周期已经封装在 `McpJsonRpcClient` 内，后续可以替换为 async 传输而不影响 `Tool` 接口。
