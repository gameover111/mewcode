# MewCode 文档索引

每一章使用同一套 Spec 驱动文档结构：

```text
spec.md -> plan.md -> task.md -> checklist.md
```

## 章节

- `ch2-initial-chat/`: 初始终端对话能力，包含 TUI、多轮上下文、OpenAI-compatible/Claude 流式 Provider。
- `ch3-tool-system/
- ch4-agent-loop/: Agent Loop — ReAct 风格多轮工具循环、plan-only 模式、取消与超时控制。`: 工具系统，包含六个核心工具、工具注册中心、OpenAI-compatible 工具调用解析和单回合 Agent 编排。

后续章节继续按 `docs/chN-topic/` 组织，避免把章节文档散落在项目根目录。
