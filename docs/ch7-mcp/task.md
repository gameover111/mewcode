# MewCode ch7 MCP 客户端 Tasks

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 改 | `pyproject.toml` | 添加 `mcp>=1.0` 依赖 |
| 新 | `mewcode/mcp/__init__.py` | 导出 Config, Manager, McpTool 等 |
| 新 | `mewcode/mcp/config.py` | Config/ServerConfig 定义 + 加载 + 展开 |
| 新 | `mewcode/mcp/manager.py` | Manager：后台 asyncio loop + 连接管理 |
| 新 | `mewcode/mcp/tool.py` | McpTool 适配器 + adapt_tool |
| 改 | `mewcode/cli.py` | 启动时加载 MCP 配置并行注册 |
| 改 | `mewcode/permissions.py` | PermissionRequest 增加 `read_only` 字段 |
| 改 | `mewcode/agent.py` | `_exec_one_checked` 透传 tool.read_only 到权限 |
| 新 | `tests/test_mcp_config.py` | 配置加载、合并、展开、非法降级 |
| 新 | `tests/test_mcp_tool.py` | adapt_tool + McpTool.execute |
| 新 | `tests/test_mcp_manager.py` | Manager 初始化和关闭 |
| 新 | `docs/ch7-mcp/spec.md` | ch7 Spec |
| 新 | `docs/ch7-mcp/plan.md` | ch7 Plan |
| 新 | `docs/ch7-mcp/task.md` | ch7 Tasks（本文件） |
| 新 | `docs/ch7-mcp/checklist.md` | ch7 Checklist |
| 新 | `.mewcode/mcp-servers.example.yaml` | MCP 标准配置示例 |
| 改 | `README.md` | 更新 MCP 配置示例为 `mcp_servers` 标准格式 |

## T1: MCP 配置

- [x] 定义 ServerConfig 和 Config dataclass
- [x] 支持 `mcp_servers` 标准格式
- [x] stdio: command、args、env；HTTP: url、headers
- [x] `${VAR}` 只展开 env/headers 的值
- [x] 用户级 `~/.mewcode/config.yaml` + 项目级 `.mewcode.yaml`
- [x] 异常降级：文件缺失/格式非法 stderr warn，不走崩溃路径
- [x] 配置校验：type/command/url 必填

## T2: Manager

- [x] 后台 asyncio event loop + daemon thread
- [x] SDK 懒加载（不配置 MCP 时不 import）
- [x] stdio_client（stdio）和 streamablehttp_client（http）两种传输
- [x] ClientSession 初始化 + initialize 握手
- [x] tools/list 列出远端工具
- [x] tools/call 通过 adapt_tool 包装
- [x] connect_timeout=30s，失败 warn 跳过
- [x] close_timeout=5s
- [x] Manager.tools() 排序返回

## T3: McpTool

- [x] 命名 `mcp__<server>__<tool>`
- [x] 非法字符校验跳过
- [x] readOnlyHint → read_only
- [x] execute() 通过 run_coroutine_threadsafe 同步桥接
- [x] 结果 text block 拼接，非 text 一次性 warn
- [x] isError 映射到 ToolResult.ok=False
- [x] 超时和异常返回 ToolResult(ok=False)
- [x] _non_text_warn_once 去重

## T4: 启动集成

- [x] CLI 创建默认 registry → 加载 MCP → 注册工具
- [x] 单 Server 失败不影响启动
- [x] Agent 调用 MCP 工具无感

## T5: 测试

- [x] 配置加载、合并、env 展开
- [x] 非法/缺失文件降级
- [x] adapt_tool 命名、schema、readOnlyHint
- [x] McpTool.execute 成功/错误/超时/混合
- [x] Manager init/close 空 cfg
- [x] pytest 通过
