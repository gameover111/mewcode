# 上下文管理 Checklist

## 实现完整性

### 包与目录结构
- [ ] C1：mewcode/compact/ 子包存在，含 compact.py / layer1.py / layer2.py / summary_prompt.py / recovery.py / token.py / state.py / const.py / __init__.py 九个核心文件
- [ ] C2：常量集中在 const.py，未散落到其他文件

### 状态对象
- [ ] C3：会话状态 new_session_context 返回实例且自动建立落盘目录，两次调用得到不同 session_id
- [ ] C4：ContentReplacementState 提供 kept/replaced/skip 三种决策，且 seen_ids 与 replacements 两本独立
- [ ] C5：CompactCircuitBreaker 有 record_success / record_failure / tripped 三个方法，连续 3 次失败后跳闸
- [ ] C6：RecoveryState 线程安全，snapshot 返回按时间倒序的副本

### 两层压缩
- [ ] C7：Layer 1 提供单条落盘、聚合落盘、幂等、决策冻结四种行为
- [ ] C8：Layer 1 落盘失败不阻断主流程，账本不记录失败 id
- [ ] C9：预览体包含原始字节数、头部预览（≤20 行且 ≤2048 字节）、落盘路径、重读提示四项
- [ ] C10：Layer 2 摘要按 <analysis> 草稿 + <summary> 正式两阶段输出，正式摘要含 9 个 ### 小节

### 恢复三段
- [ ] C11：恢复段拼装三块内容：最近读过的文件（最多 5 个）、当前可用工具、边界提示消息
- [ ] C12：边界提示消息文案稳定，连续两次调用逐字节一致

### Token 估算
- [ ] C13：estimate_tokens 支持锚点+字符增量两种来源，usage_anchor 返回 int（四字段和）
- [ ] C13a：估算远低于自动阈值时 manage_context 不进入 Layer 2

### 手动入口与命令分发
- [ ] C14：TUI 输入以 / 开头时走命令路径，不发给 LLM
- [ ] C15：Agent 暴露 run_force_compact 给 TUI 调用，签名返回 (before, after) token 数

### 紧急压缩与哨兵异常
- [ ] C16：llm.PromptTooLongError 哨兵异常存在并被 provider 包装
- [ ] C16a：紧急压缩成功后重试一次，失败则上抛不二次重试

### 配置
- [ ] C17：ProviderConfig 新增 context_window 字段并能从 YAML 解码
- [ ] C18：effective_context_window(p) 在四种场景下返回正确值

## 集成
- [ ] I1：Conversation 提供 replace_history 入口且做深拷贝
- [ ] I2：PromptTooLongError 被 Agent 主循环捕获后触发紧急压缩并重试
- [ ] I3：ReadFile 成功后 RecoveryState.record_file 被调用
- [ ] I4：/compact 命令不走 LLM，调用 run_force_compact
- [ ] I5：SessionRuntime 跨 Agent.run 轮次保持

## 编译与测试
- [ ] python -m compileall mewcode/compact 通过
- [ ] pytest tests/compact/ 全量通过
- [ ] pytest 全量通过（含既有测试）

## 端到端场景（tmux 实跑）
- [ ] 场景 1（Layer 1 截断）：MCP 工具返回 60K+ 结果，观察 [上下文] 工具结果已截断，检查 .mewcode/sessions/<id>/tool-results/ 下有对应文件，模型可以用 read_file 读取
- [ ] 场景 2（Layer 2 摘要）：构造长对话手动 /compact，观察释放 token 数合理，恢复段包含文件快照和工具列表
- [ ] 场景 3（紧急压缩）：模拟 prompt_too_long 错误，观察自动触发紧急压缩并重试成功
