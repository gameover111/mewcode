# MewCode

MewCode 是一个用 Python 构建的终端 AI 编程助手，目标是逐步做成类似 Claude Code 的 Coding Agent。
当前能力已经覆盖：
- 终端多轮对话，模型回复流式输出
- OpenAI-compatible / DeepSeek / Anthropic Claude Provider
- Claude extended thinking 配置开关
- Agent Loop：模型可多轮调用工具、读取结果、继续行动
- 6 个内置工具：读文件、写文件、替换文件、执行命令、找文件、搜代码
- plan 模式：只读规划，确认后再执行
- 模块化系统提示、环境信息注入、system-reminder
- 权限系统：黑名单、路径沙箱、规则、四档模式、人在回路
- MCP 客户端：启动时发现外部 MCP Server 工具并注册到工具中心

## 安装

```powershell
python -m pip install -e ".[dev]"
```

如果只是本地运行源码，也可以直接在项目根目录执行：
```powershell
python -m mewcode --help
```

## LLM 配置

复制示例配置：
```powershell
copy examples\config.example.yaml mewcode.yaml
```

OpenAI-compatible / DeepSeek 示例：
```yaml
name: deepseek
protocol: openai
model: deepseek-chat
base_url: https://api.deepseek.com/chat/completions
api_key: ${DEEPSEEK_API_KEY}
thinking: false
```

字段说明：
- `name`: 配置名称
- `protocol`: `openai` 或 `anthropic`
- `model`: 模型名
- `base_url`: 请求地址
- `api_key`: API Key
- `thinking`: Claude extended thinking 开关，可选
不要提交真实密钥。项目默认忽略 `.env` 和 `mewcode.yaml`。

## 启动

```powershell
python -m mewcode --config mewcode.yaml
```

常用参数：
```powershell
python -m mewcode --config mewcode.yaml --max-rounds 8
python -m mewcode --config mewcode.yaml --timeout 60
python -m mewcode --config mewcode.yaml --plan-only
python -m mewcode --config mewcode.yaml --permission-mode default
```

退出：

```text
/exit
/quit
```

## 权限模式

MewCode 当前支持四档权限模式：
| 模式 | 只读工具 | 写/改文件 | 执行命令 |
| --- | --- | --- | --- |
| `default` | 允许 | 需要确认 | 需要确认 |
| `acceptEdits` | 允许 | 允许 | 需要确认 |
| `plan` | 允许 | 需要确认 | 需要确认 |
| `bypassPermissions` | 允许 | 允许 | 允许 |

说明：
- 危险命令黑名单永久生效，`bypassPermissions` 也绕不过
- 路径沙箱永久生效，文件工具不能访问项目目录外
- `plan` 模式会只暴露只读工具，并注入规划提醒

启动时指定模式：

```powershell
python -m mewcode --config mewcode.yaml --permission-mode default
python -m mewcode --config mewcode.yaml --permission-mode acceptEdits
python -m mewcode --config mewcode.yaml --permission-mode plan
python -m mewcode --config mewcode.yaml --permission-mode bypassPermissions
```

运行时命令：

```text
/mode   # default -> acceptEdits -> plan -> bypassPermissions -> default
/plan   # 进入 plan 模式
/do     # 退出 plan，切回 default，并让模型按上文计划执行
```

## 权限规则配置

项目级示例文件：

```powershell
.mewcode\settings.yaml.example
```

推荐格式：
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

配置层级：
- 用户级：`~\.mewcode\settings.yaml`
- 项目级：`.mewcode\settings.yaml`
- 本地级：`.mewcode\settings.local.yaml`

优先级：
```text
session > local > project > user
```

本地级文件用于"永久允许"，已加入 `.gitignore`。

## 内置工具

- `read_file`: 读取工作区内文本文件
- `write_file`: 创建或覆盖工作区内文本文件
- `replace_in_file`: 原文唯一匹配替换
- `run_command`: 在工作区内执行命令
- `find_files`: 按 glob 模式查找文件
- `search_code`: 搜索代码内容

## MCP 配置

MewCode 启动时会读取 MCP Server 配置，发现远端工具并注册到工具中心。
推荐写法（使用官方 `mcp` SDK）：

```yaml
# 项目级：<root>/.mewcode.yaml
# 用户级：~/.mewcode/config.yaml

mcp_servers:
  local_demo:
    type: stdio
    command: python
    args: ["examples/mcp_server.py"]
    env:
      DEMO_TOKEN: "${DEMO_TOKEN}"

  remote_demo:
    type: http
    url: "https://example.com/mcp"
    headers:
      Authorization: "Bearer ${MCP_TOKEN}"
```

说明：
- `type`: `stdio`（本地子进程）或 `http`（远程 HTTP）
- stdio 依赖 `command`；args 和 env 可选
- http 依赖 `url`；headers 可选
- env 和 headers 支持 `${VAR}` 环境变量展开
- 项目级配置覆盖用户级配置
- 注册后的 MCP 工具名格式为 `mcp__<server>__<tool>`

ch7 只支持 MCP tools，不支持 resources、prompts、sampling。

完整配置示例见 `.mewcode/mcp-servers.example.yaml`。

## 终端验收

### 1. 基础启动

```powershell
python -m mewcode --config mewcode.yaml --permission-mode bypassPermissions
```

输入：
```text
你好
```

预期：
- 看到 `MewCode>` 后模型流式回复
- 不报错

### 2. default 权限确认

```powershell
python -m mewcode --config mewcode.yaml --permission-mode default
```

输入：
```text
请直接新建 hello_acceptance.txt，内容是 hi
```

预期：
- 出现 `[工具] 调用工具：write_file`
- 出现权限确认：
```text
[权限] 1=允许本次，2=永久允许，3=拒绝本次
```

输入：
```text
1
```

预期：
- 文件创建成功
- 模型继续输出最终回复

验收后可删除：
```powershell
del hello_acceptance.txt
```

### 3. plan 模式

启动：
```powershell
python -m mewcode --config mewcode.yaml --permission-mode plan
```

输入：
```text
先分析这个项目怎么增加一个日志功能，只给计划，不要修改文件
```

预期：
- 只使用读类工具
- 不写文件
- 最终输出计划

也可以运行中输入：
```text
/plan
```

退出 plan 并执行：

```text
/do
```

### 4. acceptEdits 模式

```powershell
python -m mewcode --config mewcode.yaml --permission-mode acceptEdits
```

输入：
```text
请新建 hello_accept_edits.txt，内容是 ok
```

预期：
- 写文件不弹权限确认
- 如果模型想执行命令，仍会弹权限确认

验收后删除：

```powershell
del hello_accept_edits.txt
```

### 5. bypass 黑名单兜底

```powershell
python -m mewcode --config mewcode.yaml --permission-mode bypassPermissions
```

输入：
```text
执行命令 rm -rf /
```

预期：
- 即使在 bypassPermissions 下，也会被危险命令黑名单拒绝
- 程序不崩溃

### 6. MCP 单元测试验收

```powershell
pytest tests/test_mcp_config.py tests/test_mcp_tool.py tests/test_mcp_manager.py -v
```

预期：
```text
22 passed
```

### 7. 全量回归

```powershell
python -m compileall mewcode
pytest
```

当前通过基线：
```text
163 passed
```

`ruff` 当前环境未安装，所以未作为本地验收项。
