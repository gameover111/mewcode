# 上下文管理 Tasks

## 文件清单

| 文件路径 | 类型 | 职责 |
|----------|------|------|
| mewcode/compact/__init__.py | 新建 | 重导出 manage_context / TriggerKind / 几个 State 类型 |
| mewcode/compact/const.py | 新建 | 全部硬编码常量 |
| mewcode/compact/state.py | 新建 | ContentReplacementState / CompactCircuitBreaker / RecoveryState / SessionContext |
| mewcode/compact/token.py | 新建 | estimate_tokens / usage_anchor / message_chars |
| mewcode/compact/layer1.py | 新建 | offload_and_snip / spill_single / build_preview |
| mewcode/compact/summary_prompt.py | 新建 | build_summary_prompt / serialize_conversation / extract_summary |
| mewcode/compact/recovery.py | 新建 | build_recovery_attachment / render_file_block / render_tools_block / BOUNDARY_NOTICE |
| mewcode/compact/layer2.py | 新建 | auto_compact / force_compact / run_summary / summarize_once / ptl_retry / pick_recent_tail / group_by_user_turn |
| mewcode/compact/compact.py | 新建 | manage_context / TriggerKind 枚举 / 编排 |
| mewcode/conversation.py | 修改 | 新增 replace_history(new_messages) 深拷贝整体替换 |
| mewcode/config.py | 修改 | ProviderConfig 追加 context_window: int = 0；追加协议默认值 |
| mewcode/compact/state.py | 新建 | SessionRuntime dataclass（compact 子包内） |
| mewcode/compact/compact.py | 新建 | TriggerKind / CompressionResult / CompactEvent |
| mewcode/agent.py | 修改 | 主循环集成 compact、ReadFile 追踪、PTL 紧急压缩、run_force_compact、_run_lock 互斥锁 |
| mewcode/providers/__init__.py | 修改 | 新增 class PromptTooLongError(Exception) 哨兵异常 |
| mewcode/providers/anthropic.py | 修改 | 把 provider 上下文过长异常包装成 PromptTooLongError |
| mewcode/providers/openai.py | 修改 | 同上 |
| mewcode/tui.py | 修改 | BUILTIN_COMMANDS 命令分发 + /exit /plan /do /compact + SessionRuntime 字段 |
| mewcode/cli.py | 修改 | 启动期构造 SessionRuntime 注入 TUI |
| .mewcode/settings.yaml.example | 修改 | 新增 context_window 字段示例 |
| .gitignore | 修改 | 追加 .mewcode/sessions/ |

## T1 - 建立 compact 子包骨架与常量

文件：mewcode/compact/__init__.py、mewcode/compact/const.py
步骤：
1. 新建目录 mewcode/compact/，添加空 __init__.py
2. 新建 const.py，定义全部硬编码常量：
   SINGLE_RESULT_LIMIT = 50000、MESSAGE_AGGREGATE_LIMIT = 200000、SUMMARY_RESERVE = 20000、
   AUTO_SAFETY_MARGIN = 13000、MANUAL_SAFETY_MARGIN = 3000、RECOVERY_FILE_LIMIT = 5、
   RECOVERY_TOKENS_PER_FILE = 5000、RECENT_KEEP_TOKENS = 10000、RECENT_KEEP_MESSAGES = 5、
   MAX_CONSECUTIVE_AUTO_COMPACT_FAILURES = 3、PTL_RETRY_LIMIT = 3、PTL_DROP_PERCENTAGE = 0.2、
   ESTIMATE_CHARS_PER_TOKEN = 3.5、PREVIEW_HEAD_BYTES = 2048、PREVIEW_HEAD_LINES = 20

## T2 - SessionContext 与目录创建

文件：mewcode/compact/state.py
步骤：
1. 定义 @dataclass class SessionContext：session_id: str / spill_dir: str
2. 实现 new_session_context(workspace: str) -> SessionContext
   - session_id = f"{int(time.time())}-{secrets.token_hex(4)}"
   - spill_dir = str(Path(workspace) / ".mewcode/sessions" / session_id / "tool-results")
   - mkdir(parents=True, exist_ok=True)

## T3 - ContentReplacementState 与 CompactCircuitBreaker

文件：mewcode/compact/state.py
步骤：
1. ContentReplacementState：__init__ 内 _seen_ids: set[str]、_replacements: dict[str, str]
2. decide_once(tool_use_id, original, decide) 原子方法
   - 已 Seen → 直接返回账本结果
   - 未 Seen → 调 decide() 回调：(kept→写 seen_ids, replaced→写 seen_ids+replacements, skip→不做任何事)
3. CompactCircuitBreaker：record_success / record_failure / tripped

## T4 - RecoveryState

文件：mewcode/compact/state.py
步骤：
1. @dataclass FileReadRecord：path / content / timestamp
2. RecoveryState：_files: dict[str, FileReadRecord]
3. record_file(path, content)：更新或追加记录，timestamp 更新为 now()
4. snapshot()：返回按时间倒序的 list[FileReadRecord]，最多 RECOVERY_FILE_LIMIT 条

## T5 - Token 估算

文件：mewcode/compact/token.py
步骤：
1. estimate_tokens(message_chars: int, anchor: int | None = None) -> int
   - 无锚点：return int(message_chars / ESTIMATE_CHARS_PER_TOKEN)
   - 有锚点：return anchor + int(delta_chars / ESTIMATE_CHARS_PER_TOKEN)
2. usage_anchor(usage) -> int：input_tokens + output_tokens + cache_read + cache_create
3. message_chars(messages) -> int：遍历消息，累计 content 的 len(s.encode("utf-8"))

## T6 - Layer 1 压缩

文件：mewcode/compact/layer1.py
步骤：
1. build_preview(content: str, spill_path: str) -> str：构造四项预览替换体
2. spill_single(session, content, tool_use_id) -> str | None：写磁盘，返回路径
3. offload_and_snip(messages, session, replacement) -> list[Message]：
   - 遍历每条 RoleTool 消息的 tool_results
   - 按字节倒序处理候选列表
   - 超过单条阈值→落盘；总和超聚合阈值→继续落盘最大项
   - 所有落盘/跳过都通过 replacement.decide_once 原子操作

## T7 - 摘要 Prompt

文件：mewcode/compact/summary_prompt.py
步骤：
1. build_summary_prompt(messages_to_summarize: list[dict]) -> str
2. 包含 <analysis> + <summary> 两阶段指令，9 个 ### 小节，禁工具指令首尾各一次
3. extract_summary(raw: str) -> str：提取 <summary>...</summary> 内的内容

## T8 - 恢复段

文件：mewcode/compact/recovery.py
步骤：
1. build_recovery_attachment(snapshot, tool_defs) -> str：组装三段恢复
2. render_file_block(record) -> str：单文件快照渲染
3. render_tools_block(tool_defs) -> str：工具列表渲染
4. BOUNDARY_NOTICE 常量：固定边界消息文案

## T9 - Layer 2 编排

文件：mewcode/compact/layer2.py
步骤：
1. pick_recent_tail(messages) -> (to_summarize, recent)：
   从尾部倒序累加，满足 token ≥ 10000 且条数 ≥ 5 后，检查不切开 tool_use/tool_result
2. group_by_user_turn(messages) -> list[list[dict]]：按"用户消息 → 后续响应"分组
3. ptl_retry(provider, messages) -> str | None：PTL 重试逻辑
4. summarize_once(provider, messages) -> str | None：单次摘要请求
5. auto_compact(conversation, runtime, provider, tool_defs) -> bool
6. force_compact(conversation, runtime, provider, tool_defs) -> tuple[int, int]

## T10 - manage_context 编排

文件：mewcode/compact/compact.py
步骤：
1. TriggerKind 枚举：AUTO / MANUAL / EMERGENCY
2. manage_context(conversation, runtime, trigger=AUTO) -> CompressionResult
   - Layer 1 → 检查熔断 → 估算 token → 触达阈值 → Layer 2 → 恢复段 → replace_history

## T11 - 集成改动

文件：mewcode/conversation.py、mewcode/config.py、mewcode/agent.py、
      mewcode/providers/__init__.py、mewcode/providers/anthropic.py、mewcode/providers/openai.py、
      mewcode/tui.py、mewcode/cli.py、.gitignore
步骤：按 spec 和 plan 实现各模块集成

### T11a - Provider 层
- mewcode/providers/__init__.py：新增 PromptTooLongError(Exception) 哨兵异常
- mewcode/providers/anthropic.py：捕获 overloaded_error → 包装为 PromptTooLongError
- mewcode/providers/openai.py：捕获 context_length_exceeded → 包装为 PromptTooLongError
- mewcode/providers/base.py：StreamEvent 增加 usage 字段

### T11b - Config 层
- mewcode/config.py：ProviderConfig 新增 context_window: int = 0；effective_context_window() 函数

### T11c - Conversation 层
- mewcode/conversation.py：新增 replace_history(new_messages) 深拷贝整体替换

### T11d - Agent 层
- mewcode/agent.py：主循环每轮前调用 manage_context；ReadFile 成功后调 RecoveryState.record_file；
  捕获 PromptTooLongError 后调 force_compact 重试一次；新增 run_force_compact 方法；新增 _run_lock

### T11e - TUI + CLI 层
- mewcode/tui.py：BUILTIN_COMMANDS 命令注册表 + /compact 处理器；SessionRuntime 字段
- mewcode/cli.py：启动期构造 SessionRuntime 注入 TUI
- .gitignore：追加 .mewcode/sessions/
