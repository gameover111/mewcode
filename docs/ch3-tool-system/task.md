# MewCode ch3 工具系统 Tasks

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `mewcode/tools/__init__.py` | 工具包导出 |
| 新建 | `mewcode/tools/base.py` | Tool、ToolResult、ToolContext、ToolError、run_tool |
| 新建 | `mewcode/tools/security.py` | 工作区路径校验、隐私文件拒读、输出截断 |
| 新建 | `mewcode/tools/file_tools.py` | 读文件、写文件、改文件工具 |
| 新建 | `mewcode/tools/search_tools.py` | 按模式找文件、搜代码内容工具 |
| 新建 | `mewcode/tools/command_tool.py` | 执行命令工具 |
| 新建 | `mewcode/tools/registry.py` | 工具注册中心和默认工具集合 |
| 新建 | `mewcode/agent.py` | 单回合工具调用编排 |
| 修改 | `mewcode/providers/base.py` | 扩展消息、请求、事件和 ToolCall |
| 修改 | `mewcode/providers/openai.py` | 请求携带工具定义，解析流式工具调用 |
| 修改 | `mewcode/conversation.py` | 支持追加 assistant/tool 工具消息 |
| 修改 | `mewcode/tui.py` | 接入 AgentEvent 和默认工具注册中心 |
| 修改 | `mewcode/cli.py` | 传入工作区根目录 |
| 新建 | `tests/test_tools_base.py` | 工具基础类型和 run_tool 测试 |
| 新建 | `tests/test_tools_security.py` | 工作区安全边界测试 |
| 新建 | `tests/test_tools_file.py` | 文件工具测试 |
| 新建 | `tests/test_tools_search.py` | 搜索工具测试 |
| 新建 | `tests/test_tools_command.py` | 命令工具测试 |
| 新建 | `tests/test_tools_registry.py` | 注册中心测试 |
| 新建 | `tests/test_openai_tool_calls.py` | OpenAI 工具调用流解析测试 |
| 新建 | `tests/test_agent_tool_flow.py` | 单回合 Agent 工具流测试 |
| 修改 | `tests/test_tui_flow.py` | TUI 接入 Agent 后的回归测试 |

## T1: 定义工具基础类型和执行包装

**文件：** `mewcode/tools/__init__.py`、`mewcode/tools/base.py`、`tests/test_tools_base.py`

**依赖：** 无

**步骤：**
1. 创建 `mewcode/tools/` 包。
2. 定义 `ToolResult`，包含 `ok`、`summary`、`data`、`error` 字段。
3. 定义 `ToolContext`，包含 `workspace`、`timeout_seconds`、`max_output_chars` 字段。
4. 定义 `Tool` Protocol，包含 `name`、`description`、`parameters_schema`、`execute`。
5. 定义 `ToolError`，表示工具可预期错误。
6. 实现 `run_tool`，捕获 `ToolError` 和其他异常，统一返回失败 `ToolResult`。
7. 编写测试覆盖成功工具、抛出 `ToolError`、抛出未知异常三种情况。

**验证：** 运行 `pytest tests/test_tools_base.py`，期望全部通过。

## T2: 实现工作区安全辅助函数

**文件：** `mewcode/tools/security.py`、`tests/test_tools_security.py`

**依赖：** T1

**步骤：**
1. 实现 `resolve_workspace_path(workspace, user_path)`，把用户路径解析到工作区绝对路径。
2. 拒绝解析后不在工作区内的路径。
3. 实现 `ensure_not_private(path)`，拒绝 `.env` 和常见密钥文件名。
4. 实现 `truncate_text(text, max_chars)`，返回截断文本和是否截断。
5. 编写测试覆盖工作区内路径、`..` 越界路径、绝对路径越界、`.env` 拒读、文本截断。

**验证：** 运行 `pytest tests/test_tools_security.py`，期望全部通过。

## T3: 实现读文件工具

**文件：** `mewcode/tools/file_tools.py`、`tests/test_tools_file.py`

**依赖：** T1、T2

**步骤：**
1. 定义 `ReadFileTool` 的名称、描述和参数 Schema。
2. 接收 `path` 参数并解析为工作区内路径。
3. 拒绝读取 `.env` 和工作区外文件。
4. 拒绝读取目录。
5. 用 UTF-8 读取文本内容，并按 `max_output_chars` 截断。
6. 返回包含 `path`、`content`、`truncated` 的成功结果。
7. 编写测试覆盖正常读取、拒读 `.env`、拒读工作区外路径、目录错误。

**验证：** 运行 `pytest tests/test_tools_file.py -k read`，期望全部通过。

## T4: 实现写文件工具

**文件：** `mewcode/tools/file_tools.py`、`tests/test_tools_file.py`

**依赖：** T1、T2

**步骤：**
1. 定义 `WriteFileTool` 的名称、描述和参数 Schema。
2. 接收 `path` 和 `content` 参数。
3. 解析路径并拒绝写入工作区外文件和 `.env`。
4. 自动创建父目录。
5. 使用 UTF-8 写入文本内容。
6. 返回包含 `path` 和写入字符数的成功结果。
7. 编写测试覆盖新建文件、覆盖文件、拒绝越界写入、拒绝写 `.env`。

**验证：** 运行 `pytest tests/test_tools_file.py -k write`，期望全部通过。

## T5: 实现改文件唯一替换工具

**文件：** `mewcode/tools/file_tools.py`、`tests/test_tools_file.py`

**依赖：** T1、T2

**步骤：**
1. 定义 `ReplaceInFileTool` 的名称、描述和参数 Schema。
2. 接收 `path`、`old_text`、`new_text` 参数。
3. 解析路径并拒绝修改工作区外文件和 `.env`。
4. 读取原文件内容。
5. 统计 `old_text` 出现次数。
6. 出现 0 次时返回清楚错误。
7. 出现多次时返回清楚错误。
8. 只在出现 1 次时替换并写回。
9. 返回包含 `path`、替换前后字符数的成功结果。
10. 编写测试覆盖唯一替换、匹配不到、多次匹配、拒绝 `.env`。

**验证：** 运行 `pytest tests/test_tools_file.py -k replace`，期望全部通过。

## T6: 实现按模式找文件工具

**文件：** `mewcode/tools/search_tools.py`、`tests/test_tools_search.py`

**依赖：** T1、T2

**步骤：**
1. 定义 `FindFilesTool` 的名称、描述和参数 Schema。
2. 接收 `pattern` 参数，使用工作区内 glob 匹配文件。
3. 只返回文件，不返回目录。
4. 返回相对工作区路径。
5. 跳过 `.git`、`__pycache__`、`.pytest_cache` 等目录。
6. 限制最多返回数量，结果过多时标记截断。
7. 编写测试覆盖普通 glob、无匹配、跳过缓存目录、结果截断。

**验证：** 运行 `pytest tests/test_tools_search.py -k find`，期望全部通过。

## T7: 实现搜代码内容工具

**文件：** `mewcode/tools/search_tools.py`、`tests/test_tools_search.py`

**依赖：** T1、T2

**步骤：**
1. 定义 `SearchCodeTool` 的名称、描述和参数 Schema。
2. 接收 `query`、可选 `regex`、可选 `pattern` 参数。
3. 遍历工作区内符合文件模式的文本文件。
4. 对每行做普通字符串搜索或正则搜索。
5. 返回匹配项列表，包含 `path`、`line`、`text`。
6. 跳过隐私文件、缓存目录和无法按文本读取的文件。
7. 限制最多匹配数量，结果过多时标记截断。
8. 编写测试覆盖普通搜索、正则搜索、文件模式限制、结果截断。

**验证：** 运行 `pytest tests/test_tools_search.py -k search`，期望全部通过。

## T8: 实现执行命令工具

**文件：** `mewcode/tools/command_tool.py`、`tests/test_tools_command.py`

**依赖：** T1、T2

**步骤：**
1. 定义 `RunCommandTool` 的名称、描述和参数 Schema。
2. 接收 `command` 和可选 `cwd` 参数。
3. 将 `cwd` 限制在工作区内，缺省为工作区根目录。
4. 使用 `subprocess.run` 独立执行命令，捕获 stdout、stderr 和退出码。
5. 应用 `ToolContext.timeout_seconds`。
6. 超时时返回结构化超时错误。
7. 对 stdout/stderr 应用输出截断。
8. 编写测试覆盖成功命令、失败退出码、超时、越界 cwd。

**验证：** 运行 `pytest tests/test_tools_command.py`，期望全部通过。

## T9: 实现工具注册中心

**文件：** `mewcode/tools/registry.py`、`tests/test_tools_registry.py`

**依赖：** T3-T8

**步骤：**
1. 定义 `ToolRegistry`，内部按工具名保存工具。
2. 实现 `register`，重复名称时报错。
3. 实现 `get`。
4. 实现 `to_openai_tools`，输出 `{"type": "function", "function": ...}` 格式。
5. 实现 `create_default_registry`，登记六个核心工具。
6. 编写测试覆盖默认六工具、按名查找、重复注册错误、OpenAI 工具定义格式。

**验证：** 运行 `pytest tests/test_tools_registry.py`，期望全部通过。

## T10: 扩展 Provider 基础数据结构

**文件：** `mewcode/providers/base.py`、`mewcode/conversation.py`、相关旧测试

**依赖：** T1

**步骤：**
1. 定义 `ToolCall` 数据类。
2. 扩展 `EventType`，加入 `tool_call`。
3. 扩展 `ProviderEvent`，增加可选 `tool_call` 字段。
4. 扩展 `MessageRole`，加入 `tool`。
5. 扩展 `ChatMessage`，增加 `tool_call_id` 和 `tool_calls` 字段。
6. 扩展 `ChatRequest`，增加 `tools` 和 `tool_choice` 字段。
7. 在 `Conversation` 中新增追加 assistant 工具调用消息和 tool 结果消息的方法。
8. 确保现有纯对话测试仍通过。

**验证：** 运行 `pytest tests/test_conversation.py tests/test_provider_factory.py tests/test_tui_flow.py`，期望全部通过。

## T11: 让 OpenAI Provider 请求携带工具定义

**文件：** `mewcode/providers/openai.py`、`tests/test_openai_tool_calls.py`、`tests/test_openai_provider.py`

**依赖：** T10

**步骤：**
1. 在构造请求体时，如果 `ChatRequest.tools` 非空，加入 `tools` 字段。
2. 支持 `tool_choice`，缺省为 `auto`。
3. 将带 `tool_calls` 的 assistant 消息转换为 OpenAI-compatible 消息格式。
4. 将 role 为 `tool` 的消息转换为包含 `tool_call_id` 的消息格式。
5. 编写测试确认请求体包含工具定义、tool_choice、assistant/tool 消息。

**验证：** 运行 `pytest tests/test_openai_tool_calls.py tests/test_openai_provider.py`，期望全部通过。

## T12: 解析 OpenAI-compatible 流式工具调用

**文件：** `mewcode/providers/openai.py`、`tests/test_openai_tool_calls.py`

**依赖：** T10、T11

**步骤：**
1. 在 `_iter_events` 中识别 `choices[].delta.tool_calls`。
2. 按 tool call index 累积 `id`、`function.name` 和 `function.arguments` 碎片。
3. 在 finish_reason 为 `tool_calls` 或流结束时产出完整 `ProviderEvent(type="tool_call")`。
4. 支持 JSON 参数分多段到达。
5. 保持普通文本流逻辑不变。
6. 编写测试覆盖单个工具调用、参数碎片拼接、文本流回归。

**验证：** 运行 `pytest tests/test_openai_tool_calls.py tests/test_openai_provider.py`，期望全部通过。

## T13: 实现单回合 Agent 编排

**文件：** `mewcode/agent.py`、`tests/test_agent_tool_flow.py`

**依赖：** T9、T10、T12

**步骤：**
1. 定义 `AgentEvent` 数据类。
2. 实现 `stream_agent_reply`。
3. 首轮请求携带 `registry.to_openai_tools()`。
4. 无工具调用时，流式转发文本并把助手文本加入会话。
5. 有工具调用时，解析 JSON 参数。
6. 未知工具或 JSON 解析失败时，构造失败 `ToolResult`。
7. 已知工具时调用 `run_tool` 执行一次工具。
8. 把 assistant 工具调用消息和 tool 结果消息加入会话。
9. 发起第二次模型请求，不携带工具定义或设置不允许工具。
10. 第二次请求只接受文本；如果再次工具调用，返回错误事件并停止。
11. 编写测试覆盖无工具、成功工具、未知工具、JSON 错误、第二次仍请求工具。

**验证：** 运行 `pytest tests/test_agent_tool_flow.py`，期望全部通过。

## T14: TUI 接入 Agent 编排

**文件：** `mewcode/tui.py`、`mewcode/cli.py`、`tests/test_tui_flow.py`

**依赖：** T13

**步骤：**
1. 修改 `run_chat_loop`，接收可选 `registry` 和 `workspace`。
2. 默认创建 `create_default_registry()`。
3. 根据 `workspace` 创建 `ToolContext`。
4. 用户输入后调用 `stream_agent_reply`。
5. 收到 `text` 事件时连续打印。
6. 收到 `tool_start` 和 `tool_result` 时打印简短中文状态。
7. 收到 `error` 时打印中文错误。
8. 修改 CLI，把当前工作目录传入 TUI。
9. 调整 TUI 测试，使用假的 Agent/Provider 验证纯对话和工具状态输出。

**验证：** 运行 `pytest tests/test_tui_flow.py tests/test_agent_tool_flow.py`，期望全部通过。

## T15: 补充 DeepSeek 工具调用端到端替代测试

**文件：** `tests/test_agent_tool_flow.py` 或新增本地测试脚本

**依赖：** T14

**步骤：**
1. 使用本地 HTTP SSE 假服务模拟 OpenAI-compatible 工具调用流。
2. 首轮返回 `read_file` 工具调用，参数分多片到达。
3. 验证 MewCode 执行读文件工具并向第二轮请求发送 tool 消息。
4. 第二轮返回最终文本。
5. 验证最终输出包含工具读取到的信息摘要。

**验证：** 运行 `pytest tests/test_agent_tool_flow.py`，期望端到端替代测试通过。

## T16: 全量验证和文档更新

**文件：** `README.md`、`docs/ch3-tool-system/checklist.md`、全项目

**依赖：** T1-T15

**步骤：**
1. 更新 README，说明工具系统、工作区边界、`.env` 拒读和单回合限制。
2. 运行 `python -m compileall mewcode`。
3. 运行 `pytest`。
4. 使用 DeepSeek 真实配置手动验证一个读文件请求。
5. 如果环境没有 tmux，记录 tmux 验收受限，并用本地 SSE 替代端到端证据补充。

**验证：** `compileall` 和 `pytest` 全部通过，并记录 DeepSeek 或本地 SSE 端到端输出摘要。

## 执行顺序

```text
T1 -> T2
      ├── T3 -> T4 -> T5
      ├── T6 -> T7
      └── T8
            -> T9

T10 -> T11 -> T12
T9 + T12 -> T13 -> T14 -> T15 -> T16
```
