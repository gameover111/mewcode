# -*- coding: utf-8 -*-
"""ch8 上下文管理 —— 硬编码常量集合（F34）"""

# 第 1 层：单条工具结果阈值（UTF-8 字节）
SINGLE_RESULT_LIMIT = 50_000

# 第 1 层：单轮聚合阈值（UTF-8 字节）
MESSAGE_AGGREGATE_LIMIT = 200_000

# 第 2 层：摘要输出预留 token 数
SUMMARY_RESERVE = 20_000

# 第 2 层：自动触发安全余量 token 数
AUTO_SAFETY_MARGIN = 13_000

# 第 2 层：手动触发安全余量 token 数
MANUAL_SAFETY_MARGIN = 3_000

# 恢复段：最近文件快照最多条数
RECOVERY_FILE_LIMIT = 5

# 恢复段：单文件快照 token 上限
RECOVERY_TOKENS_PER_FILE = 5_000

# 近期原文保留：token 下界
RECENT_KEEP_TOKENS = 10_000

# 近期原文保留：消息条数下界
RECENT_KEEP_MESSAGES = 5

# 自动摘要熔断：连续失败上限
MAX_CONSECUTIVE_AUTO_COMPACT_FAILURES = 3

# 摘要 PTL 直接重试上限
PTL_RETRY_LIMIT = 3

# 摘要 PTL 比例丢弃步长
PTL_DROP_PERCENTAGE = 0.2

# Token 估算：字符 → token 换算比（中英混排经验值）
ESTIMATE_CHARS_PER_TOKEN = 3.5

# 预览体：头部 UTF-8 字节上限
PREVIEW_HEAD_BYTES = 2_048

# 预览体：头部行数上限
PREVIEW_HEAD_LINES = 20
