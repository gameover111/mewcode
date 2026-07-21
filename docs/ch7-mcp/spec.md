# MewCode ch7 MCP 客户端 Spec

## 背景

ch6 完成后 MewCode 已有内置工具、权限系统和提示词工程化。ch7 要让 MewCode 在启动时自动发现外部 MCP Server 提供的工具，通过标准 MCP 协议注册到工具中心，Agent 调用时完全无感。

## 目标

- 使用官方 `mcp` Python SDK，不自研 JSON-RPC 协议栈
- 支持 stdio（本地子进程）和 Streamable HTTP（远程）两种传输
- MCP 工具统一命名为 `mcp__<server>__<tool>` 避免冲突
- 启动时并行连接多个 Server，单 Server 失败不影响其他
- 配置从用户级和项目级两层读取合并
- Agent/TUI 层无感知，通过统一 Tool 接口调用

## 配置格式

用户级：`~/.mewcode/config.yaml`
项目级：`<root>/.mewcode.yaml`

```yaml
mcp_servers:
  github:
    type: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
  example-http:
    type: http
    url: "https://mcp.example.com/mcp"
    headers:
      Authorization: "Bearer ${EXAMPLE_TOKEN}"
```

说明：
- 顶层键为 `mcp_servers`，值是一个 map，key 是 Server 名称
- `type` 必须显式指定，支持 `stdio` 或 `http`
- stdio 必须提供 `command`；args 和 env 可选
- http 必须提供 `url`；headers 可选
- env 和 headers 的值支持 `${VAR}` 环境变量展开，command/args/工具名不做展开
- 项目级同名 Server 完整覆盖用户级

## 功能需求

- F1: 配置解析：读取用户级和项目级 MCP 配置，合并后 `${VAR}` 展开
- F2: stdio 传输：通过 `mcp` 官方 SDK 的 `stdio_client` 启动子进程
- F3: HTTP 传输：通过官方 SDK 的 `streamablehttp_client` 发送请求
- F4: 协议流程：初始化握手 → `initialize` → `tools/list` → 注册工具 → `tools/call` 执行
- F5: 工具注册：远端工具包装为 McpTool，注册到 ToolRegistry
- F6: 失败隔离：单 Server 连接失败打 warn 跳过，不影响其他 Server
- F7: 同步桥接：当前 Agent 为同步接口，通过后台 asyncio loop + `run_coroutine_threadsafe` 桥接
- F8: 只读提示：MCP 工具 `readOnlyHint` 透传给权限系统，default 模式只读工具不弹窗确认

## 验收标准

- AC1: stdio Server 能完成 initialize → tools/list → tools/call 全流程
- AC2: HTTP Server 能完成相同全流程
- AC3: 工具名注册为 `mcp__<server>__<tool>`，避免冲突
- AC4: 项目级配置覆盖用户级；`${VAR}` 在 env/headers 中展开
- AC5: 单 Server 失败不影响启动
- AC6: `python -m compileall mewcode` 通过；`pytest` 通过
- AC7: ch6 权限系统行为不退化

## 不做的事

- MCP resources / prompts / sampling
- Server 健康检查和自动重连
- 非标准 JSON-RPC 实现
- 工具调用结果中非 text 类型的富媒体处理
