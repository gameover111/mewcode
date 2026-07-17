from __future__ import annotations

SYSTEM_REMINDER_TAG = "<system-reminder>"
SYSTEM_REMINDER_CLOSE = "</system-reminder>"

PLAN_REMINDER_INTERVAL = 4  # 规划模式完整提醒的间隔轮次

_PLAN_FULL_REMINDER = (
    "当前为 plan-only 模式。"
    "你只能使用读类工具了解项目情况，不能写文件、改文件或执行命令。"
    "请全面了解项目后输出一份详细计划供用户审批。"
)

_PLAN_SHORT_REMINDER = "plan-only（只读模式），输出计划供审批。"


def system_reminder(body: str) -> str:
    """用 <system-reminder> 标签包裹 body。"""
    return f"{SYSTEM_REMINDER_TAG}\n{body}\n{SYSTEM_REMINDER_CLOSE}"


def plan_reminder(full: bool) -> str:
    """返回已包标签的规划模式提醒。"""
    body = _PLAN_FULL_REMINDER if full else _PLAN_SHORT_REMINDER
    return system_reminder(body)


def should_inject_plan_reminder(round_index: int) -> bool:
    """
    控制规划模式提醒的注入节奏：
    - round 1: True（完整提醒）
    - (round - 1) % PLAN_REMINDER_INTERVAL == 0: True（完整提醒）
    - 其他: True（精简提醒）
    规划模式下每轮都注入（完整或精简），非规划模式不调此函数。
    """
    return True  # 规划模式下每轮都注入
