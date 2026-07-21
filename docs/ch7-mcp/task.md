# MewCode ch7 MCP 客户端 Tasks

## T1: MCP 配置

- [x] 定义 `McpServerConfig`。
- [x] 支持 `mcp.servers` 推荐格式。
- [x] 兼容 `mcp_servers` 简写格式。
- [x] 支持 stdio 的 command、args、env。
- [x] 支持 HTTP 的 url、headers。
- [x] 支持 `${VAR}` 环境变量展开。
- [x] 用户级和项目级合并，项目级覆盖用户级。

## T2: JSON-RPC 客户端

- [x] 实现自增请求 id。
- [x] 请求响应按 id 配对。
- [x] 处理 JSON-RPC error。
- [x] stdio 通过子进程 stdin/stdout 传输。
- [x] HTTP 通过 POST 传输。
- [x] HTTP 支持 JSON 响应和 SSE `data:` 响应。

## T3: MCP 会话流程

- [x] `initialize`
- [x] `notifications/initialized`
- [x] `tools/list`
- [x] `tools/call`

## T4: Tool 适配

- [x] `McpToolAdapter` 实现 MewCode `Tool` 接口。
- [x] 工具名使用 `mcp_<server>_<tool>`。
- [x] `inputSchema` 转成 `parameters_schema`。
- [x] `tools/call` 结果转为 `ToolResult`。

## T5: 启动注册

- [x] CLI 创建默认 registry。
- [x] 启动时加载 MCP Server 配置。
- [x] 自动连接并注册 MCP 工具。
- [x] 单个 Server 失败不影响启动。

## T6: 测试

- [x] stdio fake server 初始化、列工具、调用工具。
- [x] HTTP fake server 初始化、列工具、调用工具。
- [x] 配置合并和 env 展开。
- [x] 工具适配器结果转换。
- [x] 全量 pytest。
