# MewCode ch5 系统提示结构 Plan

## 架构概览

新增 mewcode/prompts/ 模块，统一管理系统提示的拼装。Agent Loop 不再直接写字符串拼 system prompt，而是调用 uild_system_prompt() 生成结构化提示。

`
mewcode/
  prompts/
    __init__.py      # 公开 build_system_prompt, build_instruction_message
    modules.py       # 七个固定模块 + 环境信息
    tools.py         # 工具描述强化（同时用在 tools 参数和 system prompt 中）
    injection.py     # 补充指令注入（[SYSTEM_NOTE] 标签）
    caching.py       # 缓存命中检测
`

### 系统提示分层

`
+-------------------------------------------+
| 稳定层（system role，可缓存）              |
|  模块1: 身份                               |
|  模块2: 系统约束                           |
|  模块3: 任务模式                           |
|  模块4: 动作执行                           |
|  模块5: 工具使用（含强化规则）             |
|  模块6: 语气风格                           |
|  模块7: 文本输出                           |
+-------------------------------------------+
| 变化层（user role [SYSTEM_NOTE]）          |
|  环境信息（工作区、OS、时间）               |
|  会话级开关指令（plan-only 精简）           |
|  补充指令（[SYSTEM_NOTE] 标签）             |
+-------------------------------------------+
`

### 模块拼装顺序（按优先级）

1. 身份 (Identity) — 你是 MewCode，一个终端 AI 编程助手。
2. 系统约束 (Constraints) — 安全边界、隐私保护
3. 任务模式 (Mode) — plan-only 等会话级开关的完整描述
4. 动作执行 (Execution) — 多轮循环行为、失败处理
5. 工具使用 (Tools) — 工具列表 + 强化规则
6. 语气风格 (Tone) — 中文回复、简洁清晰
7. 文本输出 (Output) — 格式规范、代码块
8. 环境信息 (Environment) — 工作区、OS、时间（变化层）

## 核心数据结构

`python
@dataclass
class PromptContext:
    plan_only: bool = False
    round_index: int = 0
    workspace: str = ""
    os_info: str = ""
    current_time: str = ""
    tool_registry: ToolRegistry | None = None


@dataclass
class CacheInfo:
    cached: bool = False
    cache_type: str | None = None
    raw_field: dict | None = None
`

## 模块文件设计

### mewcode/prompts/modules.py

每个模块是一个纯函数，接收 PromptContext 返回字符串（空字符串跳过该模块）：

`python
def module_identity(ctx: PromptContext) -> str: ...
def module_constraints(ctx: PromptContext) -> str: ...
def module_mode(ctx: PromptContext) -> str: ...
def module_execution(ctx: PromptContext) -> str: ...
def module_tools(ctx: PromptContext) -> str: ...
def module_tone(ctx: PromptContext) -> str: ...
def module_output(ctx: PromptContext) -> str: ...
def module_environment(ctx: PromptContext) -> str: ...
`

主拼装函数：

`python
STABLE_MODULES = [module_identity, module_constraints, ...]
ALL_MODULES = STABLE_MODULES + [module_environment]

def build_stable_prompt(ctx: PromptContext) -> str: ...
def build_environment_note(ctx: PromptContext) -> str: ...
`

### mewcode/prompts/tools.py

工具描述强化和通用规则：

`python
TOOL_RULES = {
    "read_file": "读取文件内容。优先使用此工具了解文件，而不是靠猜测。",
    "write_file": "创建或覆盖文件。如果文件已存在且有重要内容，先用 read_file 查看再决定。",
    "replace_in_file": "替换文件中唯一匹配的文本。必须先 read_file 确认原文内容。",
    "run_command": "执行终端命令。优先用专用工具完成任务而不是靠命令。",
}

TOOL_GENERAL_GUIDELINES = (
    "通用工具规则："
    "1. 编辑文件前先用 read_file 查看当前内容。"
    "2. 优先使用专用工具（read_file/write_file/replace_in_file）而非 run_command。"
    "3. run_command 中的命令不得修改用户未明确要求的文件。"
)
`

### mewcode/prompts/injection.py

`python
SYSTEM_NOTE_TAG = "[SYSTEM_NOTE]"
SYSTEM_NOTE_CLOSE = "[/SYSTEM_NOTE]"

def build_instruction_message(content: str) -> ChatMessage: ...
def should_inject_mode_instruction(ctx: PromptContext) -> bool: ...
`

注入频率规则：
- round == 1: True（完整模式指令）
- round 是偶数：True（精简版本）
- 其他：False（跳过）

### mewcode/prompts/caching.py

`python
def detect_cache_hit(event: ProviderEvent) -> CacheInfo: ...
`

### 集成到 Agent Loop

在 agent.py 中，用 PromptContext 替换原来的 system_prompt 字符串拼接：

`python
ctx = PromptContext(
    plan_only=opts.plan_only,
    round_index=state.round_index,
    workspace=str(context.workspace),
    os_info=sys.platform,
    current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    tool_registry=registry,
)

stable = build_stable_prompt(ctx)
messages = [ChatMessage(role="system", content=stable)]

if should_inject_mode_instruction(ctx):
    env_note = build_environment_note(ctx)
    messages.insert(0, build_instruction_message(env_note))

messages += conversation.snapshot()
`

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | mewcode/prompts/__init__.py | 公开接口 |
| 新建 | mewcode/prompts/modules.py | 七个模块 + 环境信息 |
| 新建 | mewcode/prompts/tools.py | 工具描述强化 |
| 新建 | mewcode/prompts/injection.py | 补充指令注入 |
| 新建 | mewcode/prompts/caching.py | 缓存命中检测 |
| 修改 | mewcode/agent.py | 集成 prompts 模块 |
| 新建 | tests/test_prompts_modules.py | 模块测试 |
| 新建 | tests/test_prompts_injection.py | 注入频率测试 |
| 新建 | tests/test_prompts_tools.py | 工具描述测试 |
| 新建 | tests/test_prompts_caching.py | 缓存检测测试 |
