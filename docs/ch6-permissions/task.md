# MewCode ch6 权限系统 Tasks

## T1: 权限基础类型

- [x] 定义 `PermissionMode` 四档：default、acceptEdits、plan、bypassPermissions。
- [x] 定义 `PermissionAction`：allow、deny、ask。
- [x] 定义 `PermissionScope`：once、session、permanent。
- [x] 定义 `ToolCategory`：read、write、exec。
- [x] 提供 `parse_permission_mode()`，兼容 strict/permissive 旧名。

## T2: 危险命令黑名单

- [x] 对 `run_command` 的 `command` 字段做正则匹配。
- [x] 覆盖 `rm -rf /`、`rm -fr ~`、fork bomb、`dd of=/dev/*`、`mkfs.*` 等高危模式。
- [x] 黑名单最高优先级，bypassPermissions 也不能绕过。

## T3: 路径沙箱

- [x] 文件类工具执行前检查路径是否在工作区内。
- [x] 先解析符号链接，再做前缀判断。
- [x] 不存在的新建路径按最近已存在祖先目录回退解析。
- [x] `run_command` 不做路径沙箱，交由黑名单、规则和模式控制。

## T4: 规则解析和配置加载

- [x] 支持推荐格式 `permissions.allow` / `permissions.deny`。
- [x] 兼容旧格式 `rules: tool(pattern): allow|deny`。
- [x] 支持友好名 Bash/Read/Write/Edit/Glob/Grep。
- [x] 支持精确匹配和 glob 匹配。
- [x] 配置缺失或非法时降级为空规则，不中断启动。
- [x] 默认模式按 local > project > user 生效。

## T5: 规则优先级

- [x] session > local > project > user。
- [x] 同层 deny 优先于 allow。
- [x] allow 规则命中后直接放行。
- [x] deny 规则命中后直接拒绝。

## T6: 模式矩阵

- [x] default：读 allow，写/命令 ask。
- [x] acceptEdits：读/写 allow，命令 ask。
- [x] plan：读 allow，写/命令 ask；Agent 只暴露只读工具。
- [x] bypassPermissions：读/写/命令 allow；黑名单和沙箱仍生效。

## T7: 人在回路

- [x] TUI 在 ask 时展示工具名、参数和原因。
- [x] 支持 `1` 允许本次。
- [x] 支持 `2` 永久允许，写入 `.mewcode/settings.local.yaml`。
- [x] 支持 `3` 拒绝本次。
- [x] EOF/Ctrl+C 时按拒绝本次处理，不崩溃。

## T8: Agent 集成

- [x] `ToolContext` 增加 `permission_manager`。
- [x] 工具执行前进行权限检查。
- [x] 未知工具先走权限判定，再返回未知工具错误。
- [x] 权限拒绝返回结构化 `ToolResult`。
- [x] 混合批次中拒绝和允许结果按原调用顺序返回。

## T9: TUI/CLI 集成

- [x] CLI 支持 `--permission-mode default|acceptEdits|plan|bypassPermissions`。
- [x] TUI 启动显示当前权限模式。
- [x] `/mode` 循环切换四档模式。
- [x] `/plan` 进入 plan 模式。
- [x] `/do` 切回 default，并注入“按计划执行”用户消息。
- [x] Windows 输出配置为 UTF-8，并处理不可编码字符。

## T10: Provider 兼容修复

- [x] OpenAI 兼容 provider 不再把 usage chunk 立即当作最终 done。
- [x] DeepSeek 风格的 `usage + tool_calls` 同 chunk 场景能先吐出 tool_call，再发 done。

## T11: 文档和示例

- [x] `.gitignore` 忽略 `.mewcode/settings.local.yaml`。
- [x] 新增 `.mewcode/settings.yaml.example`。
- [x] 更新 ch6 spec/plan/task/checklist。

## T12: 验证

- [x] `python -m compileall mewcode`
- [x] `pytest`
- [x] 真实 DeepSeek CLI：default 模式下写文件弹权限确认，允许后工具执行并继续回复。
- [ ] `ruff check .` / `ruff format --check .`：当前环境未安装 ruff，暂未执行。
- [ ] tmux 端到端：当前 Windows 环境未安装 tmux，暂未执行。
