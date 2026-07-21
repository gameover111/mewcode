# MewCode ch6 权限系统 Plan

## 架构

当前项目源码位于 `mewcode/`，因此 ch6 采用单文件权限模块 `mewcode/permissions.py`，不强行迁移到 `src/mewcode/permission/` 子包。

权限判断发生在 Agent 工具执行链路中：

1. Provider 流式输出 tool_call。
2. Agent 解析工具参数 JSON。
3. Agent 构造 `PermissionRequest`，调用 `PermissionManager.check()`。
4. 权限允许时执行真实工具。
5. 权限拒绝时返回结构化 `ToolResult(ok=False)`。
6. 工具结果回灌给对话历史，Agent Loop 继续。

provider 层不接入权限逻辑。

## 五层流水线

`PermissionManager.check()` 顺序：

1. 危险命令黑名单：仅对 `run_command` 生效，命中立即 deny。
2. 路径沙箱：仅对文件类工具生效，命中工作区外立即 deny。
3. 规则引擎：按 session、local、project、user 顺序判断。
4. 模式兜底：未命中规则时按当前权限模式给出 allow 或 ask。
5. 人在回路：ask 时通过 TUI 回调让用户选择。

短路规则：
- 黑名单 deny 不再走后续层。
- 沙箱 deny 不再走后续层。
- 显式 deny/allow 规则命中后不再走模式兜底。
- 只读工具默认不会触发 ask，除非被 deny 规则或沙箱拦截。

## 数据结构

- `PermissionMode`: `default`、`acceptEdits`、`plan`、`bypassPermissions`
- `PermissionAction`: `allow`、`deny`、`ask`
- `PermissionScope`: `once`、`session`、`permanent`
- `ToolCategory`: `read`、`write`、`exec`
- `PermissionRule`: 工具名、匹配模式、动作、来源层
- `PermissionDecision`: 是否允许、原因、动作、命中规则
- `PermissionRequest`: 工具名、参数、工作区
- `PermissionManager`: 加载规则、执行流水线、持久化永久允许

## 规则格式

推荐格式：

```yaml
default_mode: default

permissions:
  allow:
    - Bash(git *)
    - Write(src/**)
  deny:
    - Bash(git push)
    - Read(.env)
```

兼容旧格式：

```yaml
mode: default
rules:
  run_command(git *): allow
  write_file(secrets/*): deny
```

友好名映射：

| 规则名 | 内部工具 |
| --- | --- |
| Bash | run_command |
| Read | read_file |
| Write | write_file |
| Edit | replace_in_file |
| Glob | find_files |
| Grep | search_code |

## 集成点

- `mewcode/tools/base.py`: `ToolContext` 增加 `permission_manager`。
- `mewcode/agent.py`: `_exec_one_checked_v2()` 在真实工具执行前做权限检查。
- `mewcode/tui.py`: 创建 `PermissionManager`，提供人在回路输入菜单。
- `mewcode/cli.py`: 支持 `--permission-mode {default,acceptEdits,plan,bypassPermissions}`。
- `.gitignore`: 忽略 `.mewcode/settings.local.yaml`。
- `.mewcode/settings.yaml.example`: 提供项目级规则示例。

## 已修复的兼容问题

DeepSeek 兼容 OpenAI 流式接口时，可能在带 `usage` 的 chunk 中同时返回 `finish_reason=tool_calls`。原实现会过早发送 `done`，导致 Agent 丢掉后续工具调用。现在 `usage` 会暂存到最终 `[DONE]` 时再作为 done usage 发出，tool_call 会先正确回到 Agent。

Windows 控制台默认 GBK 时，模型回复中的 emoji 或特殊字符可能导致 `UnicodeEncodeError`。CLI 现在会将 stdout/stderr 配置为 UTF-8，并在 TUI 输出处做替换兜底。

## 测试

新增/更新：
- `tests/test_permissions.py`
- `tests/test_agent_permissions.py`
- `tests/test_openai_tool_calls.py`

验证命令：

```powershell
python -m compileall mewcode
pytest
python -m mewcode --config mewcode.yaml --permission-mode default
```
