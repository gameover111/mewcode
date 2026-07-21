# 上下文管理 Plan

## 架构概览

ch08 引入一个新的本地子包 mewcode.compact，作为上下文管理的唯一权威入口。包内承担三块职责：

1. 第 1 层预防性压缩：在每一轮 LLM 请求发出之前，对 mewcode.conversation 中的工具结果做幂等的"超阈值落盘 + 字符串替换"，并把替换决策冻结在一个会话级账本里，保证 prompt cache 前缀逐字节稳定。
2. 第 2 层 LLM 摘要 + 恢复：在估算 token 触达阈值（或被手动/紧急触发）时，调用 provider 跑一次结构化摘要请求，生成 9 部分摘要 + 三段恢复 + 近期原文，构造一个新的 list[Message] 替换掉旧的对话历史。
3. 辅助子模块：token 估算（锚定真实 usage + 字符增量）、最近读过文件的并发安全追踪、会话目录管理、PTL 自重试与熔断器。

mewcode.compact 不直接持有 Agent，也不直接管理 Provider。它通过一组窄接口与外部模块交互：

| 外部模块 | 交互方向 | 形式 |
|----------|----------|------|
| mewcode.agent | Agent 调 compact | 主循环每轮请求前调 manage_context；ReadFile 成功后调 RecoveryState.record_file；捕获 PromptTooLongError 后调 force_compact 重试一次 |
| mewcode.conversation | compact 改 conversation | compact 拿到 list[Message] 后做字符串替换/摘要重建，再用 replace_history 整体替换内存列表 |
| mewcode.llm | compact 调 provider | 摘要请求复用同一份 Provider.stream，但 Request.tools 留空；从 StreamEvent 尾部拿 usage 锚定 token 估算 |
| mewcode.tui | TUI 调 compact | TUI 拿到以 / 开头的输入走命令分发；/compact 命令调 compact 的 force_compact 并展示 token 变化系统消息 |
| mewcode.config | config 喂 compact | ProviderConfig 新增 context_window: int，未配置时按协议给默认值 |

### SessionRuntime

本章引入 SessionRuntime 作为 TUI Model 跨 run 持有的长生命周期状态容器：

\\\''
@dataclass
class SessionRuntime:
    replacement: ContentReplacementState
    recovery: RecoveryState
    auto_tracking: CompactCircuitBreaker
    session: SessionContext
    context_window: int = 200000
    usage_anchor: int = 0
    anchor_msg_len: int = 0
\\\''

Agent 构造期通过关键字参数 runtime: SessionRuntime 注入；TUI Model 持有同一份 SessionRuntime 跨轮复用。

## 核心数据结构

### ContentReplacementState

\\\'
class ContentReplacementState:
    def decide_once(self, tool_use_id: str, original: str,
                    decide: Callable[[], tuple[str, str]]) -> str: ...
        # 返回值：替换后的 content（kept→原文，replaced→预览字符串，skip→原文）
\\\'

- _seen_ids: set[str] — 已决策过的 tool_use_id
- _replacements: dict[str, str] — 决定替换的那些 id → 预览字符串

### CompactCircuitBreaker

\\\'
class CompactCircuitBreaker:
    def record_success(self) -> None: ...
    def record_failure(self) -> None: ...
    def tripped(self) -> bool: ...
\\\'

### RecoveryState

\\\'
@dataclass
class FileReadRecord:
    path: str
    content: str
    timestamp: datetime

class RecoveryState:
    def record_file(self, path: str, content: str) -> None: ...
    def snapshot(self) -> list[FileReadRecord]: ...
\\\'

### SessionContext

\\\'
@dataclass
class SessionContext:
    session_id: str
    spill_dir: str
\\\'

## 模块划分

\\\'
mewcode/compact/
├── __init__.py          # 重导出 manage_context / TriggerKind / 几个 State 类型
├── const.py             # 全部硬编码常量
├── state.py             # ContentReplacementState / CompactCircuitBreaker / RecoveryState / SessionContext
├── token.py             # estimate_tokens / usage_anchor / message_chars
├── layer1.py            # offload_and_snip / spill_single / build_preview
├── summary_prompt.py    # build_summary_prompt / serialize_conversation / extract_summary
├── recovery.py          # build_recovery_attachment / render_file_block / render_tools_block / BOUNDARY_NOTICE
├── layer2.py            # auto_compact / force_compact / run_summary / summarize_once / ptl_retry / pick_recent_tail / group_by_user_turn
└── compact.py           # manage_context / TriggerKind 枚举 / 编排
\\\'

## 编排逻辑

\\\'
manage_context(conversation, runtime, trigger=TriggerKind.AUTO):
  1. Layer 1: offload_and_snip(runtime.session, runtime.replacement, messages)
     对每条 RoleTool 消息的 tool_results 做：超单条阈值落盘→尚超聚合阈值继续落盘
  2. if trigger == AUTO and runtime.auto_tracking.tripped() -> return (不做 Layer 2)
  3. 估算当前总 token：
     estimated = estimate_tokens(messages, runtime.usage_anchor, runtime.anchor_msg_len)
     threshold = runtime.context_window - SUMMARY_RESERVE - (
         AUTO_SAFETY_MARGIN if trigger == AUTO else MANUAL_SAFETY_MARGIN)
  4. if estimated < threshold -> return (不触发 Layer 2)
  5. Layer 2:
     a. 确定保留尾部（pick_recent_tail）
     b. 调用 summarize_once(要摘要的部分)
        - 构造摘要 Prompt（禁工具 x2 + 分析草稿 + 9 部分模板）
        - 调 provider.stream(Request(tools=[]))
        - PTL 重试（ptl_retry）
     c. 若成功：
        - build_recovery_attachment(snapshot, tool_defs)
        - 组装新消息列表：[摘要] + [恢复段] + [近期原文]
        - conversation.replace_history(new_msgs)
        - runtime.auto_tracking.record_success()
        - usage_anchor 重置为 0
     d. 若失败：
        - runtime.auto_tracking.record_failure()（仅自动路径）
        - 不修改 conversation
  6. 返回 CompressionResult
\\\'

## 命令注册表

\\\'
BUILTIN_COMMANDS = {
    "/exit": handler_exit,
    "/plan": handler_plan,
    "/do":   handler_do,
    "/compact": handler_compact,
}
\\\'

## 摘要 Prompt 结构

\\\'
<system-reminder>
[系统指令] 你现在需要总结之前的对话历史。
重要：本次只允许输出文本摘要，不允许调用任何工具。
先写出分析草稿（放在 <analysis> 标签内），再写正式摘要（放在 <summary> 标签内）。

<summary> 内按以下结构组织：
### 主要请求和意图
### 关键技术概念
### 文件和代码段
### 错误和修复
### 问题解决过程
### 用户消息原文
### 待办任务
### 当前工作
### 可能的下一步

注意：不允许调用任何工具。
</system-reminder>
\\\'

## 边界消息

\\\'
<system-reminder>
注意：上文中部分工具结果已被截断，早期对话历史已被摘要替换。
如需查看被截断的完整文件内容，请使用文件读取工具重新读取对应路径。
如需回顾已摘要的历史细节，请使用 search_code / read_file 获取最新状态。
请不要根据摘要内容脑补不存在的代码或文件内容。
</system-reminder>
\\\'
