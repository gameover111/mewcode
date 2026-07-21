# MewCode ch7 MCP 客户端 Checklist

## 实现完整性
- [x] 配置解析：`mcp_servers` 标准格式，用户级+项目级合并
- [x] ${VAR} 展开：只展开 env/headers，不展开 command/args
- [x] stdio 传输：通过官方 SDK `stdio_client` 启动子进程
- [x] HTTP 传输：通过官方 SDK `streamablehttp_client`
- [x] 工具命名 `mcp__<server>__<tool>`，非法字符跳过
- [x] readOnlyHint 透传给权限系统
- [x] 同步桥接：后台 asyncio loop + run_coroutine_threadsafe
- [x] 结果 text block 拼接，非 text 一次性 warn
- [x] 超时/异常/远端错误返 ToolResult(ok=False)
- [x] 单 Server 失败 stderr warn 跳过，不中断启动

## 集成
- [x] CLI 启动时自动注册 MCP 工具到 registry
- [x] Agent 调用 MCP 工具无感
- [x] 权限层通过 read_only 区分 MCP 只读工具
- [x] `python -m compileall mewcode` 通过
- [x] `pytest` 通过

## 暂不做
- [x] MCP resources / prompts / sampling
- [x] 健康检查 / 自动重连
- [x] 非 text 类型处理
