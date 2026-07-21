# MewCode ch7 MCP 客户端 Checklist

## 实现完整性

- [x] 支持 stdio MCP Server。
- [x] 支持 Streamable HTTP MCP Server。
- [x] JSON-RPC 2.0 请求带 id，响应按 id 配对。
- [x] 初始化握手完成后发送 `notifications/initialized`。
- [x] 支持 `tools/list`。
- [x] 支持 `tools/call`。
- [x] MCP 工具包装为 MewCode Tool 接口。
- [x] 多 Server 独立注册，单个失败不影响其他。
- [x] 配置支持用户级和项目级合并。
- [x] env/header 支持 `${VAR}` 展开。

## 集成

- [x] CLI 启动时自动加载 MCP 配置并注册工具。
- [x] Agent 调用 MCP 工具时无感。
- [x] provider 层无 MCP 依赖。
- [x] MCP 工具名加 server 前缀，避免和内置工具冲突。

## 测试

- [x] `tests/test_mcp.py` 覆盖配置、stdio、HTTP、适配器。
- [x] `python -m compileall mewcode` 通过。
- [ ] `pytest` 通过。
- [ ] 真实或 fake MCP Server 端到端验证。

## 暂不做

- [x] 不做 resources。
- [x] 不做 prompts。
- [x] 不做 sampling。
- [x] 不做健康检查。
- [x] 不做自动重连。
