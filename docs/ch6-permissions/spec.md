# MewCode ch6 权限系统 Spec

## 背景

ch5 做完系统提示工程化后，MewCode 已经能自主多轮思考、调用工具、观察结果。但工具执行不能裸奔：文件写入、文件修改、命令执行都需要在真正执行前经过权限判断。ch6 给 MewCode 加上五层防御：危险命令黑名单、路径沙箱、规则引擎、权限模式、人在回路确认。

权限被拒绝时不终止 Agent Loop，而是作为结构化工具结果回灌给模型，让模型能调整策略。

## 目标

- 危险命令在最高优先级被硬拦截，任何规则和模式都不能放开。
- 文件类工具只能访问项目目录内路径，必须先解析符号链接，再做沙箱判断；新建文件支持最近已存在祖先目录回退。
- 支持用户级、项目级、本地级、会话级规则，优先级为 session > local > project > user，同层 deny 优先于 allow。
- 支持四档权限模式：default、acceptEdits、plan、bypassPermissions。
- 规则未明确命中且模式要求确认时，进入人在回路；支持允许本次、本会话、永久允许、拒绝本次。
- provider 层不感知权限系统，Anthropic/OpenAI/DeepSeek 兼容接口行为一致。

## 权限模式

| 模式 | 只读工具 | 写/改文件 | 执行命令 |
| --- | --- | --- | --- |
| default | allow | ask | ask |
| acceptEdits | allow | allow | ask |
| plan | allow | ask | ask |
| bypassPermissions | allow | allow | allow |

说明：
- 黑名单和路径沙箱永远优先于模式，bypassPermissions 也绕不过。
- plan 模式还会沿用 ch4/ch5 行为：只暴露只读工具，并注入规划提醒。
- 旧名兼容：strict 解析为 default，permissive 解析为 bypassPermissions；CLI 主入口只展示四档标准模式。

## 规则配置

项目级示例见 `.mewcode/settings.yaml.example`：

```yaml
default_mode: default

permissions:
  allow:
    - Bash(git *)
    - Bash(pytest)
    - Write(src/**)
  deny:
    - Bash(git push)
    - Read(.env)
    - Write(.env)
```

兼容旧格式：

```yaml
mode: default
rules:
  run_command(git *): allow
  write_file(secrets/*): deny
```

配置层级：
- 用户级：`~/.mewcode/settings.yaml`
- 项目级：`.mewcode/settings.yaml`
- 本地级：`.mewcode/settings.local.yaml`

本地级文件用于永久允许，不应提交到 git。

## 运行时切换

启动时指定：

```powershell
python -m mewcode --config mewcode.yaml --permission-mode default
python -m mewcode --config mewcode.yaml --permission-mode acceptEdits
python -m mewcode --config mewcode.yaml --permission-mode plan
python -m mewcode --config mewcode.yaml --permission-mode bypassPermissions
```

当前简化版 TUI 支持命令切换：
- `/mode`：default -> acceptEdits -> plan -> bypassPermissions -> default 循环切换。
- `/plan`：直接进入 plan 模式。
- `/do`：退出 plan，切回 default，并要求模型按上文计划执行。

## 不做

- 不做网络请求限制。
- 不做资源配额。
- 不做审计日志。
- 不做完整 Shift+Tab 状态栏 TUI；当前以 `/mode` 命令作为可用切换入口。

## 验收标准

- AC1: `rm -rf /`、`rm -fr ~`、fork bomb、写块设备等危险命令被硬拒绝，bypassPermissions 下仍拒绝。
- AC2: 工作区外路径和 symlink 逃逸被拒绝；项目内新建多级路径可放行。
- AC3: 规则支持精确匹配与 glob 匹配。
- AC4: 友好名 Bash/Read/Write/Edit/Glob/Grep 能映射到内置工具。
- AC5: session > local > project > user；同层 deny 优先。
- AC6: 配置缺失或非法时降级为空规则，不导致启动失败。
- AC7: 四档模式矩阵行为正确。
- AC8: 权限拒绝作为 ToolResult 回灌，Agent Loop 可继续。
- AC9: provider 层无权限耦合；OpenAI 兼容流式工具调用不会被 usage done 提前截断。
