# MewCode ch5 系统提示结构 验收清单

## AC1: 七个模块 + 环境信息

- [ ] build_stable_prompt() 输出包含身份模块
- [ ] 包含系统约束模块（安全边界、隐私保护）
- [ ] 包含任务模式模块
- [ ] 包含动作执行模块
- [ ] 包含工具使用模块（含强化规则）
- [ ] 包含语气风格模块
- [ ] 包含文本输出模块
- [ ] 模块之间有空行分隔
- [ ] 环境信息不在稳定 prompt 中

## AC2: 工具双重描述

- [ ] 工具描述出现在 tools 参数中（原有机制不变）
- [ ] 工具使用模块包含强化规则（编辑前先读、优先专用工具等）
- [ ] 强化规则内容与 tools 参数描述互补而非重复

## AC3: 环境信息在变化层

- [ ] build_environment_note() 输出包含工作区路径
- [ ] 包含操作系统信息
- [ ] 包含当前时间
- [ ] 环境信息不在 build_stable_prompt() 的输出中

## AC4: [SYSTEM_NOTE] 标签

- [ ] build_instruction_message() 输出用 [SYSTEM_NOTE] 标签包装
- [ ] 标签格式为 [SYSTEM_NOTE]...内容...[/SYSTEM_NOTE]
- [ ] ChatMessage 的 role 为 user

## AC5: plan-only 首轮注入

- [ ] plan_only=True, round=1 时 should_inject_mode_instruction 返回 True
- [ ] 首轮注入包含 plan-only 完整描述

## AC6: plan-only 精简注入

- [ ] plan_only=True, round=2（偶数）时 should_inject_mode_instruction 返回 True
- [ ] 偶数轮注入内容为精简版本
- [ ] plan_only=True, round=3（奇数非1）时返回 False

## AC7: 缓存命中检测

- [ ] detect_cache_hit() 能解析缓存字段
- [ ] 无缓存信息时返回 cached=False

## AC8: 现有测试兼容

- [ ] python -m compileall mewcode 无错误
- [ ] pytest 全量通过（97+ 测试）

## AC9: 模块可插拔

- [ ] 从 STABLE_MODULES 中移除某个模块后，build_stable_prompt 不再输出该模块内容
