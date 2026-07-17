# MewCode ch4 Agent Loop 验收清单

## AC1: 多轮工具调用自动执行

- [ ] Agent Loop 能在需要连续两次工具观察的任务中自动执行两轮以上工具调用
- [ ] 无需用户额外输入即可自动进入下一轮
- [ ] 每轮的工具结果正确回填到对话历史

## AC2: 无工具调用时终止并输出最终回复

- [ ] 模型响应中无 tool_call 时，Agent Loop 终止
- [ ] 输出 final 事件，内容为模型最终回复
- [ ] 输出 done 事件

## AC3: 达到最大轮数时终止

- [ ] 达到 max_rounds 时 Agent Loop 停止
- [ ] 输出含最大轮数终止原因的事件
- [ ] 不超过上限的轮次仍正常执行

## AC4: 外部取消信号

- [ ] AgentControl.cancel() 被调用后，不再发起新模型请求
- [ ] 取消后不再执行新工具
- [ ] 输出 cancelled 事件
- [ ] 已执行完的工具结果可保留，未执行的不伪造

## AC5: 超时终止

- [ ] 达到 overall_timeout_seconds 时停止循环
- [ ] 达到 per_round_timeout_seconds 时停止本轮
- [ ] 输出含超时原因的事件

## AC6: 事件流完整性

- [ ] 事件流包含 user_message、text、tool_start、tool_result、final、done
- [ ] 每个事件携带正确的 round_index
- [ ] tool_start 和 tool_result 携带 tool_call_id 和 tool_name

## AC7: thinking 事件

- [ ] 模型返回 thinking 内容时，Agent 输出 thinking 事件
- [ ] thinking 内容对上层可见

## AC8: 读类工具并发执行

- [ ] 同一轮中多个读类工具（read_file、find_files、search_code）并行执行
- [ ] 执行结果按原始 tool_call 顺序返回
- [ ] 并发执行比串行更快（在有多工具时验证）

## AC9: 写类工具串行执行

- [ ] 同一轮中多个写类工具（write_file、replace_in_file、run_command）按顺序串行执行
- [ ] 先执行的工具结果不影响后执行工具的入参（但结果按顺序回填）

## AC10: plan-only + 读类工具可执行

- [ ] plan_only=True 时读类工具正常执行
- [ ] 读类工具的执行结果回填给模型

## AC11: plan-only + 写类工具被拦截

- [ ] plan_only=True 时写类工具不被实际执行
- [ ] 不修改文件系统、不执行命令
- [ ] 返回结构化拦截结果（含 plan-only 提示）

## AC12: plan-only 最终输出计划

- [ ] plan-only 模式下模型最终回复是一份计划
- [ ] 回复明确说明需要用户审批后才能执行写操作
- [ ] 不会有已执行写操作的虚假声明

## AC13: 工具失败回填让模型调整

- [ ] 工具执行失败时，失败结果结构化回填到对话
- [ ] 失败原因（如文件不存在、语法错误）包含在结果中
- [ ] 模型下一轮能看到失败细节并调整策略

## AC14: tool_call_id 一一对应

- [ ] 每个工具结果的 tool_call_id 与模型请求中的对应
- [ ] 工具结果回填到 Conversation 时使用正确的 ID

## AC15: ToolExecutionHooks 可观测

- [ ] before_tool hook 在工具执行前被调用
- [ ] after_tool hook 在工具执行后被调用
- [ ] hook 返回值可跳过真实工具执行
- [ ] 测试能替身观测到 hook 调用

## AC16: ch3 单工具任务兼容

- [ ] 已有 ch3 的单工具请求能通过 Agent Loop 完成
- [ ] 行为结果与 ch3 一致（工具执行 + 最终回复）

## 非功能验证

- [ ] python -m compileall mewcode 无错误
- [ ] pytest 全部通过
- [ ] DeepSeek 端到端验证：多轮工具调用能正常完成
- [ ] DeepSeek plan-only 验证：写类工具被拦截，输出计划
