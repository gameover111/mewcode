# MewCode ch6 权限系统 Checklist

## 实现完整性

- [x] 黑名单硬拦截：`rm -rf /`、`rm -fr ~`、fork bomb、写块设备等命令判 Deny。
- [x] 黑名单不可绕过：bypassPermissions 模式下危险命令仍判 Deny。
- [x] 沙箱围栏：项目根之外路径被拒绝，项目内路径可放行。
- [x] 沙箱防逃逸：项目内 symlink 指向项目外时判 Deny（当前 Windows 无 symlink 权限时测试 skip）。
- [x] 沙箱新建文件祖先回退：项目内多级未创建路径可正常通过权限判断。
- [x] 规则精确与 glob 匹配：`Bash(git status)`、`Bash(git *)`、`Write(src/**)` 行为正确。
- [x] deny 规则正向拦截。
- [x] 同层 deny 优先于 allow。
- [x] 友好名路由：Bash/Read/Write/Edit/Glob/Grep 映射到 6 个内置工具。
- [x] 模式矩阵：default、acceptEdits、plan、bypassPermissions 按读/写/命令分类裁决。
- [x] 流水线短路：黑名单、沙箱、显式规则命中后不继续后续层。
- [x] 安全默认：未知工具、坏参数、类别不明不会静默放行。

## 集成

- [x] 拒绝回灌不中断：权限拒绝返回 `ToolResult(ok=False)`，Agent Loop 可继续。
- [x] 保序配对回灌：同批次拒绝和允许结果按原调用顺序返回。
- [x] 人在回路三选一：`1` 允许本次，`2` 永久允许，`3` 拒绝本次。
- [x] 永久放行持久化：写入 `.mewcode/settings.local.yaml`，重载后生效。
- [x] 层级就近优先：session > local > project > user。
- [x] 配置降级：配置缺失或非法时按空规则降级，不抛未捕获异常。
- [x] 跨协议一致：权限系统在 Agent 层，provider 层不依赖权限模块。
- [x] OpenAI/DeepSeek 流式兼容：usage chunk 不会提前截断 tool_calls。
- [x] 不破坏 ch04/ch05：全量 pytest 通过。

## 模式切换

- [x] 启动参数支持：
  - `--permission-mode default`
  - `--permission-mode acceptEdits`
  - `--permission-mode plan`
  - `--permission-mode bypassPermissions`
- [x] 运行时 `/mode` 循环切换：default -> acceptEdits -> plan -> bypassPermissions -> default。
- [x] `/plan` 进入 plan 模式。
- [x] `/do` 退出 plan，切回 default，并让模型按上文计划执行。
- [ ] Shift+Tab 状态栏式切换：当前简化 TUI 未实现，暂用 `/mode` 替代。

## 编译与测试

- [x] `python -m compileall mewcode` 通过。
- [x] `pytest` 通过：`137 passed, 1 skipped`。
- [x] `python -m mewcode --help` 显示四档权限模式。
- [x] 真实 DeepSeek CLI 验证：default 模式写文件弹权限确认，输入 `1` 后成功执行并继续回复。
- [ ] `ruff check .`：当前环境未安装 ruff，未执行。
- [ ] `ruff format --check .`：当前环境未安装 ruff，未执行。
- [ ] tmux 端到端：当前 Windows 环境未安装 tmux，未执行。

## 端到端场景

- [x] 场景 1：default 写文件触发权限确认；允许本次后文件写入，Loop 继续。
- [x] 场景 2：bypassPermissions 下普通对话不阻塞。
- [x] 场景 3：模型输出 emoji 时 Windows 控制台不再因编码崩溃。
- [x] 场景 4：DeepSeek 工具调用不会因 usage done 提前结束而空回复。
- [ ] 场景 5：tmux 自动端到端；本机没有 tmux。
