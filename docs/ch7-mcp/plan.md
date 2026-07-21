# MewCode ch7 MCP 客户端 Plan

## 架构

新增 `mewcode/mcp/` 子包，包含三个模块：

```
mewcode/mcp/
├── __init__.py      # 导出 Config, Manager, McpTool, load_config, new_manager
├── config.py        # Config 加载、合并、${VAR} 展开
├── manager.py       # Manager：后台 asyncio loop，连接管理
└── tool.py          # McpTool 适配器，adapt_tool
```

启动链路：
1. `cli.py` 加载 LLM Provider 配置
2. 创建默认 ToolRegistry（6 个内置工具）
3. `mcp.load_config()` 读取用户级和项目级 MCP 配置
4. `mcp.new_manager()` 启动后台 Manager，并行连接 Server
5. 每个 MCP 工具通过 `adapt_tool()` 包装为 McpTool，注册进 registry
6. TUI/Agent 使用同一 registry，调用时无感

## 模块设计

### config.py

- `ServerConfig`: type, command, args, env, url, headers
- `Config`: servers 字典
- `load_config(root)`: 读 `~/.mewcode/config.yaml` + `<root>/.mewcode.yaml`
- `_load_file()` 异常降级为空字典
- `_merge_servers()` 项目级覆盖用户级
- `_expand_vars()` 只展开 env/headers 的值
- `_validate_server()` 校验每个 server

### manager.py

- `Manager`: 持有后台 asyncio loop + thread
- `new_manager(cfg, version)`: 创建 Manager，开始连接
- `connect_timeout=30s`, `close_timeout=5s`
- `_connect_one()`: 单 Server 连接，失败/超时不抛主流程
- `_do_connect()`: SDK 初始化流程
- `_enter_transport()`: stdio→`stdio_client`，http→`streamablehttp_client`
- `Manager.close()`: 5s 兜底关闭

### tool.py

- `McpTool`: 实现 Tool Protocol，因当前为同步接口，`execute()` 通过后台 loop 调用 async
- `adapt_tool(server_name, tool, session, loop)`: 包装远端工具
- 命名 `mcp__<server>__<tool>`，非法字符跳过
- `readOnlyHint` → McpTool.read_only → 权限系统
- 结果收集 text block 拼接，非 text 一次性 warn 后丢弃
- 超时/异常返回 ToolResult(ok=False)

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| MCP 协议实现 | 官方 `mcp` SDK | 不自研 JSON-RPC，SDK 已处理握手/id配对/传输 |
| Manager 架构 | 后台 asyncio loop + thread | Tool 接口同步，SDK 是 async，后台 loop 桥接 |
| 配置字段 | `mcp_servers` 顶层键 | 标准 MCP 配置约定 |
| 工具命名 | `mcp__<server>__<tool>` | 双下划线清晰分隔 server/tool，避免冲突 |
| read_only 传递 | McpTool.read_only → PermissionRequest.read_only | 让 MCP 只读工具 default 模式不弹窗 |
| 单 Server 故障 | stderr warn + 跳过 | 不阻塞主流程 |
| 只展开 env/headers | `${VAR}` 不展开 command/args | 安全性：command/args 不信任外部变量 |
