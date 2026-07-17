# MewCode ch3 工具系统 Plan

## 架构概览
ch3 在当前纯对话架构上新增三层：工具层、工具调用 Provider 适配层、单回合 Agent 编排层。

工具层位于 `mewcode/tools/`，负责定义统一 Tool 接口、工具参数 Schema、结构化执行结果、工作区安全边界和六个核心工具。工具层不依赖具体模型 API，只接收普通参数并返回结构化结果。

Provider 适配层扩展现有 `ChatProvider` 事件模型，使 OpenAI-compatible Provider 能发送工具定义，并解析流式工具调用事件。Claude Provider 本章保持纯对话能力，不做 Claude 工具调用端到端适配。

单回合 Agent 编排层位于 `mewcode/agent.py`，负责一次用户输入后的完整流程：先向模型发起带工具定义的请求；如果模型没有请求工具，直接流式输出文本；如果模型请求工具，执行一次工具，把结果追加进对话历史，再请求模型生成最终回复。本章明确不进入第二轮工具调用。

TUI 层继续负责输入输出，但不直接处理工具细节。TUI 调用 Agent 编排层，接收文本流、工具状态提示和错误提示。

## 核心数据结构

### ToolResult
```python
@dataclass(frozen=True)
class ToolResult:
    ok: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
```
所有工具统一返回结构化结果。`summary` 给模型和用户快速理解，`data` 放机器可读字段，`error` 放失败原因。

### ToolContext
```python
@dataclass(frozen=True)
class ToolContext:
    workspace: Path
    timeout_seconds: float = 10.0
    max_output_chars: int = 20000
```
保存工具执行的公共上下文，包括工作区根目录、默认超时和输出大小限制。

### Tool
```python
class Tool(Protocol):
    name: str
    description: str
    parameters_schema: dict[str, Any]

    def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        ...
```
统一工具接口。每个工具负责校验自己的参数并返回 `ToolResult`，异常由工具执行包装层捕获。

### ToolRegistry
```python
class ToolRegistry:
    def register(self, tool: Tool) -> None: ...
    def get(self, name: str) -> Tool | None: ...
    def to_openai_tools(self) -> list[dict[str, Any]]: ...
```
集中登记工具，按名称查找，并转换成 OpenAI-compatible `tools` 列表。

### ToolCall
```python
@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments_json: str
```
表示模型在一次响应中请求的工具调用。`arguments_json` 是流式碎片拼接后的完整 JSON 字符串。

### ProviderEvent
现有 `ProviderEvent` 扩展事件类型：
```python
EventType = Literal["text", "thinking", "tool_call", "error", "done"]

@dataclass(frozen=True)
class ProviderEvent:
    type: EventType
    content: str = ""
    tool_call: ToolCall | None = None
```
当模型完成工具调用输出时，Provider 产出 `tool_call` 事件。文本和 done 行为保持兼容。

### ChatMessage
现有 `ChatMessage` 扩展角色和工具字段：
```python
MessageRole = Literal["user", "assistant", "tool"]

@dataclass(frozen=True)
class ChatMessage:
    role: MessageRole
    content: str
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None
```
OpenAI-compatible API 需要 assistant 消息携带 `tool_calls`，tool 消息携带 `tool_call_id`。纯文本对话继续只使用 `role` 和 `content`。

### ChatRequest
现有 `ChatRequest` 增加可选工具定义和工具选择：
```python
@dataclass(frozen=True)
class ChatRequest:
    messages: list[ChatMessage]
    config: ProviderConfig
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | None = "auto"
```
当 `tools` 为空时保持现有纯对话请求；当提供工具列表时，OpenAI Provider 将其放入请求体。

### AgentEvent
```python
@dataclass(frozen=True)
class AgentEvent:
    type: Literal["text", "tool_start", "tool_result", "error", "done"]
    content: str = ""
```
Agent 编排层对 TUI 输出的统一事件。TUI 只消费 AgentEvent，不关心 Provider 与工具内部细节。

## 模块设计

### `mewcode/tools/base.py`
**职责：** 定义 `Tool`、`ToolResult`、`ToolContext`、`ToolError` 和工具执行包装函数。

**对外接口：**
```python
def run_tool(tool: Tool, arguments: dict[str, Any], context: ToolContext) -> ToolResult
```

**依赖：** 标准库 dataclasses、pathlib、typing。

### `mewcode/tools/security.py`
**职责：** 处理工作区路径解析、越界检查、隐私文件拒读、输出截断。

**对外接口：**
```python
def resolve_workspace_path(workspace: Path, user_path: str) -> Path
def ensure_not_private(path: Path) -> None
def truncate_text(text: str, max_chars: int) -> tuple[str, bool]
```

**依赖：** 标准库 pathlib。

### `mewcode/tools/file_tools.py`
**职责：** 实现读文件、写文件、改文件三个工具。

**对外接口：**
```python
class ReadFileTool: ...
class WriteFileTool: ...
class ReplaceInFileTool: ...
```

**依赖：** `Tool` 基础接口、安全模块。

### `mewcode/tools/search_tools.py`
**职责：** 实现按 glob 找文件和搜代码内容工具。

**对外接口：**
```python
class FindFilesTool: ...
class SearchCodeTool: ...
```

**依赖：** pathlib、re、安全模块。

### `mewcode/tools/command_tool.py`
**职责：** 实现执行命令工具，带工作区限制、超时、退出码、stdout/stderr 捕获。

**对外接口：**
```python
class RunCommandTool: ...
```

**依赖：** subprocess、安全模块。

### `mewcode/tools/registry.py`
**职责：** 管理工具注册、查找和 OpenAI-compatible 工具定义转换。

**对外接口：**
```python
def create_default_registry() -> ToolRegistry
```

**依赖：** 六个工具类。

### `mewcode/providers/base.py`
**职责：** 扩展 `ChatMessage`、`ChatRequest`、`ProviderEvent`，加入工具调用相关字段。

**对外接口：** 保持现有类名，增加字段和 `ToolCall`。

**依赖：** 标准库 dataclasses、typing。

### `mewcode/providers/openai.py`
**职责：** 在请求体中携带工具定义，解析 OpenAI-compatible 流式 `tool_calls` 参数碎片，并产出 `tool_call` 事件。

**对外接口：**
```python
class OpenAIProvider:
    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]: ...
```

**依赖：** `ToolCall`、SSE 解析。

### `mewcode/agent.py`
**职责：** 单回合工具调用编排：发起首轮模型请求、执行至多一次工具、回灌工具结果、发起最终回复请求。

**对外接口：**
```python
def stream_agent_reply(
    conversation: Conversation,
    config: ProviderConfig,
    provider: ChatProvider,
    registry: ToolRegistry,
    context: ToolContext,
) -> Iterator[AgentEvent]
```

**依赖：** Provider、Conversation、ToolRegistry、ToolContext。

### `mewcode/tui.py`
**职责：** 从直接调用 Provider 改为调用 Agent 编排层，显示工具执行状态和最终文本。

**对外接口：**
```python
def run_chat_loop(..., registry: ToolRegistry | None = None, workspace: Path | None = None) -> int
```

**依赖：** Agent、默认工具注册中心。

## 模块交互
1. CLI 启动时创建默认工具注册中心，并把工作区根目录传给 TUI。
2. 用户输入消息后，TUI 将用户消息加入 `Conversation`。
3. TUI 调用 `stream_agent_reply(...)`。
4. Agent 用注册中心生成 OpenAI-compatible 工具定义，构造首轮 `ChatRequest`。
5. Provider 发起流式请求。
6. 如果 Provider 返回文本事件，Agent 直接转发给 TUI，并在结束后把助手回复加入会话。
7. 如果 Provider 返回工具调用事件，Agent 停止首轮文本输出，解析参数并查找工具。
8. Agent 执行一次工具，将 `ToolResult` 序列化为 JSON 文本。
9. Agent 向会话追加一条带 `tool_calls` 的 assistant 消息和一条 tool 消息。
10. Agent 发起第二次模型请求，不携带工具定义或强制禁止工具，让模型生成最终回复。
11. Provider 的最终文本流由 Agent 转发给 TUI，最终助手文本加入会话。
12. 如果第二次模型仍请求工具，Agent 返回错误事件并停止，符合“本章不做 Agent Loop”边界。

## 文件组织
```text
mewcode/
├── docs/
│   └── ch3-tool-system/
│       ├── spec.md
│       ├── plan.md
│       ├── task.md
│       └── checklist.md
├── mewcode/
│   ├── agent.py
│   ├── tui.py
│   ├── providers/
│   │   ├── base.py
│   │   └── openai.py
│   └── tools/
│       ├── __init__.py
│       ├── base.py
│       ├── security.py
│       ├── file_tools.py
│       ├── search_tools.py
│       ├── command_tool.py
│       └── registry.py
└── tests/
    ├── test_tools_file.py
    ├── test_tools_search.py
    ├── test_tools_command.py
    ├── test_tools_registry.py
    ├── test_openai_tool_calls.py
    └── test_agent_tool_flow.py
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 工具调用目标协议 | 先支持 OpenAI-compatible/DeepSeek 工具调用 | 用户当前可用真实账号是 DeepSeek，且现有 Provider 已支持 OpenAI-compatible 流式接口 |
| 工具结果格式 | `ToolResult` 转 JSON 放入 tool 消息 content | 结构化、易测试，也符合 OpenAI-compatible 工具结果回灌方式 |
| 文件安全边界 | 默认限制在当前工作区，并拒读 `.env` | 防止模型越界读取隐私文件，符合用户隐私要求 |
| 改文件策略 | 原文唯一匹配替换 | 与用户要求一致，失败时给模型明确重试信息 |
| 命令执行 | `subprocess.run(..., timeout=...)` 独立进程 | 简单可控，本章不做 shell 会话保持 |
| 搜索实现 | Python pathlib/re 实现，后续可优化为 ripgrep | 避免依赖外部命令，Windows 环境可稳定测试 |
| 输出截断 | 工具层统一截断大输出并标记 `truncated` | 避免把过大内容塞入模型上下文 |
| Agent Loop | 固定最多一次工具调用回合 | 严格遵守 ch3 边界，下一章再做自动循环 |
| TUI 职责 | TUI 只消费 AgentEvent | 保持界面层简单，工具细节留给 Agent 和工具层 |

## Spec 覆盖检查
- F1-F2: `Tool`、`ToolRegistry`、默认注册中心覆盖。
- F3-F5: `ReadFileTool`、`WriteFileTool`、`ReplaceInFileTool` 覆盖。
- F6: `RunCommandTool` 覆盖。
- F7-F8: `FindFilesTool`、`SearchCodeTool` 覆盖。
- F9-F10: `ToolContext`、安全模块、`run_tool` 覆盖。
- F11-F12: `ChatRequest.tools`、OpenAI Provider 工具定义与流式工具调用解析覆盖。
- F13-F14: `stream_agent_reply` 工具执行与回灌覆盖。
- F15: Agent 无工具调用分支保持纯对话覆盖。
- F16: Agent 未知工具和 JSON 解析错误分支覆盖。
