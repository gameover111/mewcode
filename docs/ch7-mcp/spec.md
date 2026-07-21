# MewCode ch7 MCP 客户端 Spec

## 背景

ch6 后 MewCode 已经有内置工具和权限系统。ch7 要让 MewCode 能在启动时发现外部 MCP Server 提供的工具，并把它们包装成 MewCode 现有 `Tool` 接口注册进工具中心。Agent 调用时不需要知道工具来自本地还是 MCP。

## 目标

- 支持 MCP stdio 本地子进程传输。
- 支持 MCP Streamable HTTP 远程传输。
- 使用 JSON-RPC 2.0 消息格式，按请求 id 配对响应。
- 会话流程包含 initialize、notifications/initialized、tools/list、tools/call。
- MCP 工具通过适配器接入 `ToolRegistry`。
- 多个 Server 独立连接和注册；单个 Server 失败不影响其他 Server。
- 从用户级、项目级配置合并 Server 列表，项目级覆盖用户级。

## 配置格式

推荐写在项目 `mewcode.yaml` 或用户级 `~/.mewcode/settings.yaml`：

```yaml
mcp:
  servers:
    local_demo:
      transport: stdio
      command: python
      args: ["examples/mcp_server.py"]
      env:
        DEMO_TOKEN: ${DEMO_TOKEN}

    remote_demo:
      transport: http
      url: https://example.com/mcp
      headers:
        Authorization: Bearer ${MCP_TOKEN}
```

兼容简写：

```yaml
mcp_servers:
  local_demo:
    command: python
    args: ["server.py"]
```

## 功能需求

- F1: 解析用户级和项目级 MCP Server 配置，并进行 `${VAR}` 环境变量展开。
- F2: stdio 传输启动本地子进程，通过 stdin/stdout 收发换行分隔 JSON-RPC。
- F3: HTTP 传输通过 POST 发送 JSON-RPC，请求头支持配置。
- F4: JSON-RPC 请求 id 自增，响应按 id 关联。
- F5: 客户端初始化后调用 `tools/list` 获取工具。
- F6: 每个远端工具包装为 `McpToolAdapter` 并注册到 `ToolRegistry`。
- F7: Agent 调用 MCP 工具时执行 `tools/call`，结果转换为 `ToolResult`。
- F8: 单个 Server 初始化、列工具或调用失败时，不影响其他 Server。

## 不做

- 不做 MCP resources。
- 不做 MCP prompts。
- 不做 MCP sampling。
- 不做健康检查。
- 不做自动重连。

## 验收标准

- AC1: stdio Server 能完成 initialize、tools/list、tools/call。
- AC2: HTTP Server 能完成 initialize、tools/list、tools/call。
- AC3: 工具名注册为 `mcp_<server>_<tool>`，避免和内置工具冲突。
- AC4: 配置合并时项目级覆盖用户级。
- AC5: env/header 中的 `${VAR}` 能展开。
- AC6: Server 失败时启动不中断。
- AC7: `pytest` 通过，既有内置工具和 Agent Loop 不退化。
