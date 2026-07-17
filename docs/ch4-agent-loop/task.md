# MewCode ch4 Agent Loop Tasks

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `mewcode/agent_tools.py` | 工具分类、plan-only 拦截、多工具执行调度、权限 hook |
| 修改 | `mewcode/agent.py` | 从单回合升级为 ReAct Agent Loop |
| 修改 | `mewcode/providers/openai.py` | 保持/验证一轮多个 tool call 流解析 |
| 修改 | `mewcode/tui.py` | 消费扩展 AgentEvent，传入 AgentOptions/AgentControl |
| 修改 | `mewcode/cli.py` | 增加 `--max-rounds`、`--plan-only`、`--timeout` |
| 新建 | `tests/test_agent_tool_scheduler.py` | 工具分类、并发/串行、hooks 测试 |
| 新建 | `tests/test_agent_loop.py` | ReAct 多轮循环和终止条件测试 |
| 新建 | `tests/test_agent_plan_only.py` | plan-only 读类允许、写类拦截测试 |
| 新建 | `tests/test_agent_cancel_timeout.py` | 取消和超时测试 |
| 修改 | `tests/test_agent_tool_flow.py` | 旧 ch3 单回合测试迁移到 Agent Loop 语义 |
| 修改 | `tests/test_openai_tool_calls.py` | 多 tool call 解析测试 |
| 修改 | `tests/test_tui_flow.py` | TUI 新事件和 CLI 参数回归测试 |

## T1: 定义 Agent Loop 选项、控制和事件类型

**文件：** `mewcode/agent.py`、`tests/test_agent_loop.py`

**依赖：** 无

**步骤：**
1. 定义 `AgentOptions`，包含 `max_rounds`、`plan_only`、`overall_timeout_seconds`、`per_round_timeout_seconds`。
2. 定义 `AgentControl`，包含 `cancelled` 和 `cancel()`。
3. 定义 `AgentRunState`，记录 `round_index`、`terminate_reason`、`started_at`。
4. 扩展 `AgentEvent`，加入 `user_message`、`thinking`、`final`、`cancelled`，并增加 `round_index`、`tool_call_id`、`tool_name` 字段。
5. 保持原有 `text`、`tool_start`、`tool_result`、`error`、`done` 事件兼容。
6. 编写测试确认默认 options、cancel 控制和事件字段可创建。

**验证：** 运行 `pytest tests/test_agent_loop.py -k types`，期望通过。

## T2: 实现工具分类和 plan-only 拦截

**文件：** `mewcode/agent_tools.py`、`tests/test_agent_tool_scheduler.py`、`tests/test_agent_plan_only.py`

**依赖：** T1

**步骤：**
1. 定义 `ToolKind`，取值 `read` 和 `write`。
2. 实现 `tool_kind(tool_name)` 固定映射。
3. 将 `read_file`、`find_files`、`search_code` 归为读类。
4. 将 `write_file`、`replace_in_file`、`run_command` 归为写类。
5. 未知工具默认归为写类，偏保守。
6. 定义 `ToolExecutionHooks`，包含 `before_tool` 和 `after_tool`。
7. 实现 plan-only 写类拦截，返回结构化 `ToolResult`，不调用真实工具。
8. 编写测试覆盖工具分类、未知工具、plan-only 读类允许、写类拦截。

**验证：** 运行 `pytest tests/test_agent_tool_scheduler.py tests/test_agent_plan_only.py -k classify`，期望通过。

## T3: 实现多工具执行调度

**文件：** `mewcode/agent_tools.py`、`tests/test_agent_tool_scheduler.py`

**依赖：** T2

**步骤：**
1. 实现 `execute_tool_calls(...)`，输入多个 `ToolCall`。
2. 对读类工具使用 `ThreadPoolExecutor` 并发执行。
3. 对写类工具按原始顺序串行执行。
4. 调度前调用 `before_tool` hook；hook 返回 `ToolResult` 时跳过真实工具执行。
5. 调度后调用 `after_tool` hook。
6. 所有返回结果按原始 tool call 顺序排列。
7. 未知工具返回结构化错误结果。
8. JSON 参数错误返回结构化错误结果。
9. 编写测试覆盖读类并发、写类串行、顺序回填、hooks 调用、未知工具、JSON 错误。

**验证：** 运行 `pytest tests/test_agent_tool_scheduler.py`，期望通过。

## T4: 支持 OpenAI Provider 一轮多个 tool call

**文件：** `mewcode/providers/openai.py`、`tests/test_openai_tool_calls.py`

**依赖：** T1

**步骤：**
1. 检查现有 `_flush_tool_calls` 是否会产出多个 `tool_call` 事件。
2. 增加测试：同一流中返回两个不同 index 的 tool call。
3. 确认每个 tool call 的 id、name、arguments_json 都正确。
4. 确认 `[DONE]` 时不会重复产出已 flush 的 tool call。

**验证：** 运行 `pytest tests/test_openai_tool_calls.py`，期望通过。

## T5: 将 Agent 从单回合改为 ReAct 循环

**文件：** `mewcode/agent.py`、`tests/test_agent_loop.py`、`tests/test_agent_tool_flow.py`

**依赖：** T3、T4

**步骤：**
1. 将 `stream_agent_reply` 改为 for/while 循环，最多执行 `options.max_rounds` 轮。
2. 每轮创建 `ChatRequest`，携带工具定义和 `tool_choice="auto"`。
3. 每轮收集 Provider 返回的文本、thinking 和全部 tool_call。
4. 无 tool_call 时，将本轮文本作为最终回复，写入会话并终止。
5. 有 tool_call 时，将 assistant tool_call 消息写入会话。
6. 调用 `execute_tool_calls` 执行本轮所有工具。
7. 按原始顺序写入 tool 结果消息。
8. 进入下一轮。
9. 编写测试覆盖两轮工具调用后最终回复、无工具立即终止、ch3 单工具任务仍可完成。

**验证：** 运行 `pytest tests/test_agent_loop.py tests/test_agent_tool_flow.py`，期望通过。

## T6: 实现最大轮数终止

**文件：** `mewcode/agent.py`、`tests/test_agent_loop.py`

**依赖：** T5

**步骤：**
1. 在每轮开始前检查是否超过 `max_rounds`。
2. 达到上限时发出 `error` 事件，内容说明达到最大轮数。
3. 发出 `done` 事件，终止循环。
4. 记录终止原因便于测试。
5. 编写测试：Provider 每轮都请求工具，`max_rounds=2` 时停止。

**验证：** 运行 `pytest tests/test_agent_loop.py -k max_rounds`，期望通过。

## T7: 实现取消控制

**文件：** `mewcode/agent.py`、`tests/test_agent_cancel_timeout.py`

**依赖：** T5

**步骤：**
1. 在每轮开始前检查 `control.cancelled`。
2. 在模型事件处理过程中检查取消。
3. 在工具执行前检查取消。
4. 取消时发出 `cancelled` 和 `done` 事件。
5. 确保取消后不再发起新的模型请求。
6. 编写测试覆盖开始前取消、首轮后取消、工具前取消。

**验证：** 运行 `pytest tests/test_agent_cancel_timeout.py -k cancel`，期望通过。

## T8: 实现整体超时和每轮超时

**文件：** `mewcode/agent.py`、`tests/test_agent_cancel_timeout.py`

**依赖：** T5

**步骤：**
1. 用 `time.monotonic()` 记录整体开始时间。
2. 每轮开始和工具执行前检查整体超时。
3. 每轮开始记录 round start，检查每轮超时。
4. 超时时发出 `error` 和 `done` 事件。
5. 编写测试覆盖整体超时和每轮超时。

**验证：** 运行 `pytest tests/test_agent_cancel_timeout.py -k timeout`，期望通过。

## T9: 实现 thinking 和最终回复事件

**文件：** `mewcode/agent.py`、`tests/test_agent_loop.py`

**依赖：** T5

**步骤：**
1. Provider 返回 `thinking` 时发出 `AgentEvent(type="thinking")`。
2. 无 tool_call 终止时发出 `final` 事件，内容为最终回复。
3. 保持 `text` 流式事件不变。
4. 编写测试确认 thinking、text、final、done 的顺序。

**验证：** 运行 `pytest tests/test_agent_loop.py -k events`，期望通过。

## T10: plan-only 模式集成到 Agent Loop

**文件：** `mewcode/agent.py`、`mewcode/agent_tools.py`、`tests/test_agent_plan_only.py`

**依赖：** T3、T5

**步骤：**
1. 将 `options.plan_only` 传给 `execute_tool_calls`。
2. plan-only 下读类工具照常执行。
3. plan-only 下写类工具被拦截，返回结构化结果。
4. 在最小 system prompt 中提示模型 plan-only 模式最终输出计划，不能宣称已执行写操作。
5. 编写测试覆盖读类允许、写类文件未被修改、最终回复包含计划/审批含义。

**验证：** 运行 `pytest tests/test_agent_plan_only.py`，期望通过。

## T11: TUI 接入扩展事件和取消

**文件：** `mewcode/tui.py`、`tests/test_tui_flow.py`

**依赖：** T5、T7、T9

**步骤：**
1. `run_chat_loop` 接收 `AgentOptions`。
2. 创建 `AgentControl` 并传入 `stream_agent_reply`。
3. KeyboardInterrupt 时调用 `control.cancel()` 并显示取消提示。
4. 消费 `thinking` 事件并显示 `[思考]`。
5. 消费 `final` 事件，不重复打印已经流式输出的文本。
6. 消费 `cancelled` 事件并显示中文取消提示。
7. 保持 `text` 连续打印。
8. 调整 TUI 测试覆盖纯对话、工具状态、取消事件、plan-only 参数传递。

**验证：** 运行 `pytest tests/test_tui_flow.py`，期望通过。

## T12: CLI 增加 Agent Loop 参数

**文件：** `mewcode/cli.py`、`tests/test_tui_flow.py` 或新增 CLI 测试

**依赖：** T11

**步骤：**
1. 增加 `--max-rounds`，默认 8。
2. 增加 `--plan-only` 布尔开关。
3. 增加 `--timeout`，映射整体超时秒数。
4. 将参数构造成 `AgentOptions` 传给 TUI。
5. 验证 `python -m mewcode --help` 展示三个新参数。

**验证：** 运行 `python -m mewcode --help`，期望看到 `--max-rounds`、`--plan-only`、`--timeout`。

## T13: 本地 SSE 端到端替代测试

**文件：** `tests/test_agent_loop.py` 或新增端到端测试文件

**依赖：** T12

**步骤：**
1. 使用 `httpx.MockTransport` 模拟 OpenAI-compatible SSE。
2. 第 1 轮返回两个读类工具调用。
3. 验证两个读类工具结果都回填。
4. 第 2 轮返回一个写类工具调用。
5. 验证写类工具串行执行并回填。
6. 第 3 轮返回最终文本。
7. 验证最终事件和会话消息完整。

**验证：** 运行 `pytest tests/test_agent_loop.py -k e2e`，期望通过。

## T14: README 和文档索引更新

**文件：** `README.md`、`docs/README.md`

**依赖：** T12

**步骤：**
1. README 增加 Agent Loop 简介。
2. README 增加 `--max-rounds`、`--plan-only`、`--timeout` 示例。
3. README 说明 plan-only 只允许读类工具，写类会被拦截。
4. docs 索引加入 `ch4-agent-loop/`。

**验证：** 阅读 README 和 `docs/README.md`，确认 ch4 信息存在。

## T15: 全量验证与真实 DeepSeek 试跑

**文件：** 全项目

**依赖：** T1-T14

**步骤：**
1. 运行 `python -m compileall mewcode`。
2. 运行 `pytest`。
3. 用本地 DeepSeek 配置试跑一个需要两步观察的请求。
4. 用 `--plan-only` 试跑一个涉及写文件的请求，确认写类被拦截或模型给出计划。
5. 如果网络审批受限，记录本地 SSE 端到端测试证据。

**验证：** compileall 和 pytest 全通过；DeepSeek 或本地 SSE 输出满足 checklist。

## 执行顺序

```text
T1 -> T2 -> T3 -> T5
              ├── T6
              ├── T7
              ├── T8
              ├── T9
              └── T10
T4 ───────────┘
T5-T10 -> T11 -> T12 -> T13 -> T14 -> T15
```
