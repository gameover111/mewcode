# MewCode ch5 系统提示结构 Tasks

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | mewcode/prompts/__init__.py | 公开 build_system_prompt, build_environment_note, detect_cache_hit |
| 新建 | mewcode/prompts/modules.py | 七个固定模块 + 环境信息模块 + PromptContext |
| 新建 | mewcode/prompts/tools.py | 工具描述强化 + 通用规则 |
| 新建 | mewcode/prompts/injection.py | [SYSTEM_NOTE] 标签注入 + 频率控制 |
| 新建 | mewcode/prompts/caching.py | 缓存命中检测 |
| 修改 | mewcode/agent.py | 集成 prompts 模块 |
| 新建 | tests/test_prompts_modules.py | 模块拼装、插拔、环境信息 |
| 新建 | tests/test_prompts_injection.py | 标签格式、注入频率 |
| 新建 | tests/test_prompts_tools.py | 工具描述强化内容 |
| 新建 | tests/test_prompts_caching.py | 缓存检测解析 |

## T1: 定义 PromptContext 和模块基础

文件: mewcode/prompts/__init__.py, mewcode/prompts/modules.py

依赖: 无

1. 定义 PromptContext 数据类
2. 实现八个模块函数，每个返回字符串
3. 定义 STABLE_MODULES 列表和 ALL_MODULES
4. 实现 build_stable_prompt: 遍历 STABLE_MODULES，空字符串跳过，非空之间加空行
5. 实现 build_environment_note: 环境信息 + 可选模式提示
6. 外部接口: __init__.py 导出 build_stable_prompt 和 build_environment_note

验证: pytest tests/test_prompts_modules.py

## T2: 工具描述强化

文件: mewcode/prompts/tools.py

依赖: T1

1. 实现 TOOL_RULES 字典，每个工具名称到强化描述的映射
2. 实现 TOOL_GENERAL_GUIDELINES 字符串，通用规则
3. 实现 get_tool_descriptions() 返回强化版工具列表
4. 实现 get_tool_guidelines() 返回通用规则

验证: pytest tests/test_prompts_tools.py

## T3: 补充指令注入

文件: mewcode/prompts/injection.py

依赖: T1

1. 定义 SYSTEM_NOTE_TAG 和 SYSTEM_NOTE_CLOSE
2. 实现 build_instruction_message(content) -> ChatMessage
3. 实现 should_inject_mode_instruction(ctx) 频率控制:
   - round == 1: True（完整指令）
   - round % 2 == 0: True（精简指令）
   - 其他: False
4. 实现 get_mode_instruction(ctx) 返回当前模式指令文本

验证: pytest tests/test_prompts_injection.py

## T4: 缓存命中检测

文件: mewcode/prompts/caching.py

依赖: 无

1. 定义 CacheInfo 数据类
2. 实现 detect_cache_hit(event: ProviderEvent) -> CacheInfo
3. 检查 ProviderEvent 的 content 中是否包含缓存相关字段（如 OpenAI 的 usage）
4. 当前作为检测点，不影响流程

验证: pytest tests/test_prompts_caching.py

## T5: 集成到 Agent Loop

文件: mewcode/agent.py

依赖: T1-T4

1. 导入 prompts 模块
2. 在 stream_agent_reply 中构建 PromptContext
3. 用 build_stable_prompt 替换原来的 system_prompt 字符串
4. 按 should_inject_mode_instruction 决定是否注入环境/模式指令
5. 用 build_instruction_message 包装变化层内容
6. 保持与现有测试的兼容性

验证: pytest tests/test_agent_*.py tests/test_tui_flow.py

## T6: 完整测试套件验证

文件: 全部

依赖: T5

1. pytest 全量运行
2. python -m compileall mewcode
3. 确认现有 97+ 测试全部通过

## 执行顺序

T1 -> T2 -> T3 -> T4 -> T5 -> T6
