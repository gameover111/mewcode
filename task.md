# MewCode 初始对话能力 Tasks

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `pyproject.toml` | 项目元数据、依赖、测试配置、控制台入口 |
| 新建 | `README.md` | 基础启动说明和配置示例说明 |
| 新建 | `examples/config.example.yaml` | YAML 配置样例 |
| 新建 | `mewcode/__init__.py` | 包初始化和版本信息 |
| 新建 | `mewcode/__main__.py` | `python -m mewcode` 入口 |
| 新建 | `mewcode/cli.py` | 参数解析、配置加载、Provider 创建、TUI 启动 |
| 新建 | `mewcode/config.py` | YAML 配置读取与校验 |
| 新建 | `mewcode/conversation.py` | 多轮会话历史管理 |
| 新建 | `mewcode/tui.py` | 基础终端交互和流式输出 |
| 新建 | `mewcode/providers/__init__.py` | Provider 包导出 |
| 新建 | `mewcode/providers/base.py` | ProviderConfig、ChatMessage、ChatRequest、ProviderEvent、ChatProvider |
| 新建 | `mewcode/providers/factory.py` | 根据协议创建 Provider |
| 新建 | `mewcode/providers/sse.py` | SSE data 行解析 |
| 新建 | `mewcode/providers/anthropic.py` | Claude 流式 Provider |
| 新建 | `mewcode/providers/openai.py` | OpenAI 流式 Provider |
| 新建 | `tests/test_config.py` | 配置加载与错误校验测试 |
| 新建 | `tests/test_conversation.py` | 会话历史测试 |
| 新建 | `tests/test_provider_factory.py` | Provider 工厂测试 |
| 新建 | `tests/test_sse.py` | SSE 解析测试 |
| 新建 | `tests/test_anthropic_provider.py` | Claude Provider 请求体和流解析测试 |
| 新建 | `tests/test_openai_provider.py` | OpenAI Provider 请求体和流解析测试 |
| 新建 | `tests/test_tui_flow.py` | TUI 多轮与流式输出测试 |

## T1: 初始化 Python 项目骨架

**文件：** `pyproject.toml`、`README.md`、`examples/config.example.yaml`、`mewcode/__init__.py`、`mewcode/__main__.py`、`mewcode/providers/__init__.py`

**依赖：** 无

**步骤：**
1. 创建 Python 包目录 `mewcode/` 和 `mewcode/providers/`。
2. 在 `pyproject.toml` 中声明项目名、Python 版本、运行依赖 `httpx`、`PyYAML`、开发测试依赖 `pytest`。
3. 在 `pyproject.toml` 中配置 `mewcode = "mewcode.cli:main"` 控制台入口。
4. 在 `mewcode/__main__.py` 中调用 `mewcode.cli.main`，使 `python -m mewcode` 可用。
5. 在 `README.md` 写入最小启动说明和当前阶段边界。
6. 在 `examples/config.example.yaml` 写入六个配置字段的示例。

**验证：** 运行 `python -m compileall mewcode`，期望编译通过；运行 `python -m mewcode --help`，期望显示帮助信息。

## T2: 定义 Provider 基础数据结构和接口

**文件：** `mewcode/providers/base.py`

**依赖：** T1

**步骤：**
1. 定义 `ProviderConfig` 数据类，包含 `name`、`protocol`、`model`、`base_url`、`api_key`、`thinking` 字段。
2. 定义 `ChatMessage` 数据类，包含 `role` 和 `content` 字段。
3. 定义 `ChatRequest` 数据类，包含 `messages` 和 `config` 字段。
4. 定义 `ProviderEvent` 数据类，包含 `type` 和 `content` 字段。
5. 定义 `ChatProvider` Protocol，包含 `stream_chat` 方法签名。
6. 定义 `ProviderError` 异常类，用于向上层传递可理解错误。

**验证：** 运行 `python -m compileall mewcode/providers/base.py`，期望编译通过。

## T3: 实现 YAML 配置加载与校验

**文件：** `mewcode/config.py`、`tests/test_config.py`

**依赖：** T2

**步骤：**
1. 实现 `load_provider_config(path)`，读取 YAML 文件。
2. 校验 `name`、`protocol`、`model`、`base_url`、`api_key` 为必填字段。
3. 校验 `protocol` 只接受 `anthropic` 或 `openai`。
4. 将缺省 `thinking` 转为 `False`。
5. 对缺文件、YAML 格式错误、字段缺失、协议不支持返回中文错误。
6. 编写测试覆盖正常配置、缺省 `thinking`、缺必填字段、不支持协议。

**验证：** 运行 `pytest tests/test_config.py`，期望全部通过。

## T4: 实现会话历史管理

**文件：** `mewcode/conversation.py`、`tests/test_conversation.py`

**依赖：** T2

**步骤：**
1. 实现 `Conversation` 数据类，内部保存 `ChatMessage` 列表。
2. 实现 `add_user_message`，追加用户消息。
3. 实现 `add_assistant_message`，追加助手消息。
4. 实现 `snapshot`，返回消息列表副本。
5. 编写测试确认多轮消息顺序正确，且修改快照不会污染原始会话。

**验证：** 运行 `pytest tests/test_conversation.py`，期望全部通过。

## T5: 实现 SSE 数据行解析

**文件：** `mewcode/providers/sse.py`、`tests/test_sse.py`

**依赖：** T2

**步骤：**
1. 实现 `iter_sse_data_lines(response)`，逐行读取 HTTP 流式响应。
2. 只产出以 `data:` 开头的内容，去掉前缀和首尾空白。
3. 忽略空行、注释行和非 `data:` 行。
4. 保留 `[DONE]` 这类结束标记，由具体 Provider 决定如何处理。
5. 编写测试覆盖普通 data 行、空行、注释行、多事件连续输出。

**验证：** 运行 `pytest tests/test_sse.py`，期望全部通过。

## T6: 实现 Provider 工厂

**文件：** `mewcode/providers/factory.py`、`tests/test_provider_factory.py`

**依赖：** T2

**步骤：**
1. 实现 `create_provider(config)`。
2. 当 `protocol` 为 `anthropic` 时返回 `ClaudeProvider`。
3. 当 `protocol` 为 `openai` 时返回 `OpenAIProvider`。
4. 当协议不支持时抛出中文 `ProviderError`。
5. 编写测试确认两种协议返回正确类型，不支持协议返回清晰错误。

**验证：** 运行 `pytest tests/test_provider_factory.py`，期望全部通过。

## T7: 实现 Claude 流式 Provider

**文件：** `mewcode/providers/anthropic.py`、`tests/test_anthropic_provider.py`

**依赖：** T2、T5

**步骤：**
1. 实现 `ClaudeProvider`，构造时允许注入 `httpx.Client` 以便测试。
2. 将 `ChatRequest.messages` 转换为 Claude Messages API 请求体。
3. 设置 `model`、`messages`、`stream: true`。
4. 当 `config.thinking` 为 `True` 时，在请求体中加入 Claude extended thinking 配置。
5. 使用 `x-api-key` 和 `anthropic-version` 请求头认证。
6. 解析 Claude SSE 事件，将文本增量转换为 `ProviderEvent(type="text")`。
7. 将 thinking 增量转换为 `ProviderEvent(type="thinking")`。
8. 将网络错误、HTTP 错误、未知事件解析错误转换为中文 `ProviderError` 或 `error` 事件。
9. 编写测试确认请求 URL、请求头、请求体、thinking 配置和文本流解析正确。

**验证：** 运行 `pytest tests/test_anthropic_provider.py`，期望全部通过。

## T8: 实现 OpenAI 流式 Provider

**文件：** `mewcode/providers/openai.py`、`tests/test_openai_provider.py`

**依赖：** T2、T5

**步骤：**
1. 实现 `OpenAIProvider`，构造时允许注入 `httpx.Client` 以便测试。
2. 将 `ChatRequest.messages` 转换为 OpenAI Chat Completions 请求体。
3. 设置 `model`、`messages`、`stream: true`。
4. 使用 `Authorization: Bearer ...` 请求头认证。
5. 解析 OpenAI SSE `choices[].delta.content`，转换为 `ProviderEvent(type="text")`。
6. 遇到 `[DONE]` 时输出 `ProviderEvent(type="done")` 并结束。
7. 将网络错误、HTTP 错误、未知事件解析错误转换为中文 `ProviderError` 或 `error` 事件。
8. 编写测试确认请求 URL、请求头、请求体和文本流解析正确。

**验证：** 运行 `pytest tests/test_openai_provider.py`，期望全部通过。

## T9: 实现基础 TUI 对话循环

**文件：** `mewcode/tui.py`、`tests/test_tui_flow.py`

**依赖：** T2、T4

**步骤：**
1. 实现 `run_chat_loop(config, provider)`。
2. 启动时显示中文欢迎信息、当前配置名和退出提示。
3. 循环读取用户输入，空输入时继续等待。
4. 支持 `/exit` 和 `/quit` 退出。
5. 用户输入后追加到 `Conversation`。
6. 调用 `provider.stream_chat(ChatRequest(...))`。
7. 收到 `text` 事件时立即打印并累计助手回复。
8. 收到 `thinking` 事件时以清晰但不干扰正文的方式显示。
9. 收到错误时显示中文错误信息。
10. 本轮结束后将完整助手回复加入会话。
11. 编写测试使用假的 Provider 验证多轮上下文、流式打印和退出行为。

**验证：** 运行 `pytest tests/test_tui_flow.py`，期望全部通过。

## T10: 实现 CLI 启动编排

**文件：** `mewcode/cli.py`、`mewcode/__main__.py`

**依赖：** T3、T6、T9

**步骤：**
1. 用 `argparse` 实现 `--config` 参数。
2. 默认配置路径使用 `mewcode.yaml`。
3. 调用 `load_provider_config` 加载配置。
4. 调用 `create_provider` 创建 Provider。
5. 调用 `run_chat_loop` 进入交互界面。
6. 捕获配置错误和 Provider 创建错误，显示中文错误并返回非零退出码。
7. 确保 `python -m mewcode --help` 和控制台入口都走同一个 `main`。

**验证：** 运行 `python -m mewcode --help`，期望显示 `--config` 参数；运行缺失配置文件场景，期望显示中文错误且退出码非零。

## T11: 补齐集成测试与文档示例

**文件：** `README.md`、`examples/config.example.yaml`、`tests/test_tui_flow.py`

**依赖：** T1-T10

**步骤：**
1. 在 README 中补充安装依赖、复制配置、启动命令、退出命令。
2. 确认 `examples/config.example.yaml` 同时说明 `anthropic` 和 `openai` 的写法。
3. 补充一个 TUI 集成测试，使用假 Provider 模拟两段流式输出。
4. 确认 README 明确本阶段不包含 tool use、文件操作、代码编辑。

**验证：** 运行 `pytest tests/test_tui_flow.py`，期望集成场景通过。

## T12: 运行全量验证

**文件：** 全项目

**依赖：** T1-T11

**步骤：**
1. 运行 `python -m compileall mewcode`。
2. 运行 `pytest`。
3. 运行 `python -m mewcode --help`。
4. 准备后续 checklist 要求的 tmux 端到端测试。

**验证：** 三个命令均通过，并记录输出摘要。

## 执行顺序

```text
T1
├── T2
│   ├── T3
│   ├── T4
│   ├── T5
│   │   ├── T7
│   │   └── T8
│   └── T6
├── T9
│   └── T10
└── T11
    └── T12
```
