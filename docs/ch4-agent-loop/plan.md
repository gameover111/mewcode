# MewCode ch4 Agent Loop Plan

## 架构概览
ch4 在 ch3 工具系统之上，把 `mewcode/agent.py` 从“单回合工具调用编排”升级为 ReAct Agent Loop。核心循环为：发起模型请求、收集模型事件、如果有工具调用则执行工具并回填结果、继续下一轮；如果没有工具调用或触发终止条件则结束。

Agent Loop 对外只暴露 `AgentEvent` 事件流。TUI/CLI 不理解 Provider 细节、不直接执行工具，只消费用户消息、thinking、文本、工具状态、最终回复、错误和结束事件。

工具执行从单个工具扩展为一轮多个工具调用。工具注册中心增加工具分类，读类工具允许并发执行，写类工具串行执行。plan-only 模式下，读类工具正常执行，写类工具在执行前被拦截并返回结构化失败结果。

取消与超时通过轻量 `AgentControl` 对象处理。循环每轮开始、模型事件处理前、工具执行前后检查取消与截止时间，确保取消后不再启动新模型请求或新工具执行。

## 核心数据结构

### AgentOptions
```python
@dataclass(frozen=True)
class AgentOptions:
    max_rounds: int = 8
    plan_only: bool = False
    overall_timeout_seconds: float | None = None
    per_round_timeout_seconds: float | None = None
```
控制循环上限、plan-only 和超时。默认保持实用但保守。

### AgentControl
```python
@dataclass
class AgentControl:
    cancelled: bool = False

    def cancel(self) -> None: ...
```
外部取消信号。TUI 后续可以在用户中断时调用 `cancel()`。

### AgentRunState
```python
@dataclass
class AgentRunState:
    round_index: int = 0
    terminate_reason: str | None = None
    started_at: float = field(default_factory=time.monotonic)
```
记录循环状态，便于测试终止原因和轮次。

### AgentEvent
扩展现有事件类型：
```python
AgentEventType = Literal[
    "user_message",
    "thinking",
    "text",
    "tool_start",
    "tool_result",
    "final",
    "error",
    "cancelled",
    "done",
]

@dataclass(frozen=True)
class AgentEvent:
    type: AgentEventType
    content: str = ""
    round_index: int | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
```
事件中携带轮次和工具信息，方便 TUI 展示与测试断言。

### ToolKind
```python
ToolKind = Literal["read", "write"]
```
工具分类。读类包括 `read_file`、`find_files`、`search_code`；写类包括 `write_file`、`replace_in_file`、`run_command`。

### ToolExecutionHooks
```python
@dataclass
class ToolExecutionHooks:
    before_tool: Callable[[ToolCall], ToolResult | None] | None = None
    after_tool: Callable[[ToolCall, ToolResult], None] | None = None
```
权限策略预留位。本章只提供调用点，不实现具体权限规则。

### ChatRequest
沿用 ch3 的 `ChatRequest`，但 Agent Loop 每轮都携带工具定义，除非进入最终无工具请求或后续策略要求禁用工具。

### ProviderEvent
沿用 ch3 的 ProviderEvent，但 OpenAI Provider 需要支持一轮返回多个 `tool_call` 事件。

## 模块设计

### `mewcode/agent.py`
**职责：** 实现 ReAct Agent Loop、事件流输出、终止判断、取消和超时检查。

**对外接口：**
```python
def stream_agent_reply(
    conversation: Conversation,
    config: ProviderConfig,
    provider: ChatProvider,
    registry: ToolRegistry,
    context: ToolContext,
    options: AgentOptions | None = None,
    control: AgentControl | None = None,
    hooks: ToolExecutionHooks | None = None,
) -> Iterator[AgentEvent]:
    ...
```

**依赖：** Provider、Conversation、ToolRegistry、工具执行调度模块。

### `mewcode/agent_tools.py`
**职责：** 工具分类、plan-only 拦截、多工具调度执行、结果按原始顺序回填。

**对外接口：**
```python
def tool_kind(tool_name: str) -> ToolKind
def execute_tool_calls(
    tool_calls: list[ToolCall],
    registry: ToolRegistry,
    context: ToolContext,
    plan_only: bool,
    hooks: ToolExecutionHooks | None = None,
) -> list[tuple[ToolCall, ToolResult]]
```

**依赖：** `ThreadPoolExecutor`、工具注册中心、`run_tool`。

### `mewcode/providers/openai.py`
**职责：** 扩展流式工具调用解析，支持同一响应中多个 tool call。

**变更点：**
- `_flush_tool_calls` 返回多个 `ProviderEvent(type="tool_call")`。
- `Agent Loop` 收集一轮中的全部 tool call，而不是遇到第一个就中断。

### `mewcode/tui.py`
**职责：** 消费扩展后的 `AgentEvent`，展示 thinking、工具状态、最终回复、取消/错误。

**变更点：**
- 支持 plan-only 启动参数传入。
- KeyboardInterrupt 时通过 `AgentControl.cancel()` 请求取消。

### `mewcode/cli.py`
**职责：** 增加 Agent Loop 相关 CLI 参数。

**新增参数：**
```text
--max-rounds N
--plan-only
--timeout SECONDS
```

### `mewcode/tools/registry.py`
**职责：** 可选增加工具分类查询，或由 `agent_tools.py` 用固定映射分类。

**决策：** 本章使用 `agent_tools.py` 固定映射，避免修改所有工具类。

## 模块交互
1. 用户输入消息，TUI 将用户消息加入 `Conversation`，并调用 `stream_agent_reply`。
2. Agent 发出 `user_message` 事件。
3. Agent 进入第 1 轮，请求 Provider，携带工具定义和最小 system prompt 约束。
4. Provider 流式返回 thinking、文本和零个或多个 tool call。
5. Agent 转发 thinking/text 事件，并收集本轮全部 tool call。
6. 如果没有 tool call，Agent 把文本作为最终回复，发出 `final` 和 `done` 事件后终止。
7. 如果有 tool call，Agent 调用 `execute_tool_calls`。
8. 调度器按读类和写类分组：读类用线程池并发，写类按原顺序串行。
9. plan-only 下写类工具不执行，直接生成结构化拦截结果。
10. Agent 按原始 tool call 顺序把 assistant tool call 消息和 tool 结果消息写入 `Conversation`。
11. Agent 判断取消、超时、最大轮数；未终止则进入下一轮。
12. 达到终止条件时，Agent 发出对应 `error/cancelled/done` 事件。

## 文件组织
```text
mewcode/
├── docs/
│   └── ch4-agent-loop/
│       ├── spec.md
│       ├── plan.md
│       ├── task.md
│       └── checklist.md
├── mewcode/
│   ├── agent.py
│   ├── agent_tools.py
│   ├── cli.py
│   ├── tui.py
│   └── providers/
│       └── openai.py
└── tests/
    ├── test_agent_loop.py
    ├── test_agent_tool_scheduler.py
    ├── test_agent_plan_only.py
    ├── test_agent_cancel_timeout.py
    ├── test_openai_tool_calls.py
    └── test_tui_flow.py
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 循环模型 | ReAct：LLM -> tool -> observation -> next LLM | 与用户目标一致，且能复用 ch3 工具回填 |
| 事件流 | Python Iterator 产出 `AgentEvent` | 与当前同步 TUI/Provider 风格一致，改动小 |
| 取消 | `AgentControl.cancelled` 轻量标志 | 当前代码是同步生成器，先用简单可测的取消机制 |
| 超时 | Agent 层用 monotonic 截止时间，工具层沿用 `ToolContext.timeout_seconds` | 避免引入 async，保持 Windows 稳定 |
| 并发 | `ThreadPoolExecutor` 只并发读类工具 | 读类无副作用，可提升效率；写类串行防止冲突 |
| 工具分类 | 固定映射在 `agent_tools.py` | 六个工具数量少，避免过早修改 Tool 接口 |
| plan-only | 调度器拦截写类工具，返回失败 ToolResult | 保证不会执行副作用，同时模型能看到原因并产出计划 |
| 权限策略 | hooks 预留 before/after，不实现规则 | 满足本章边界，为后续章节留接口 |
| Provider 多工具 | OpenAI Provider 产出多个 tool_call 事件，Agent 负责收集 | 保持 Provider 简单，循环逻辑集中在 Agent |

## Spec 覆盖检查
- F1-F4: `stream_agent_reply` 循环、终止判断和状态事件覆盖。
- F5-F7: `AgentOptions`、`AgentControl`、超时检查覆盖。
- F8-F11: Provider 多 tool call 解析和 `agent_tools.execute_tool_calls` 覆盖。
- F12-F14: plan-only 拦截和最终回复约束覆盖。
- F15-F16: 无工具最终回复和 thinking 事件覆盖。
- F17: 工具失败回填下一轮覆盖。
- F18: `ToolExecutionHooks` 覆盖。
