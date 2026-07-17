from __future__ import annotations

from mewcode.prompts.reminder import (
    system_reminder,
    plan_reminder,
    should_inject_plan_reminder,
    PLAN_REMINDER_INTERVAL,
    SYSTEM_REMINDER_TAG,
    SYSTEM_REMINDER_CLOSE,
)


def test_system_reminder_has_tags():
    result = system_reminder("test body")
    assert SYSTEM_REMINDER_TAG in result
    assert SYSTEM_REMINDER_CLOSE in result
    assert "test body" in result


def test_plan_reminder_full_contains_detailed_text():
    result = plan_reminder(full=True)
    assert "<system-reminder>" in result
    assert "plan-only" in result
    assert "读类工具" in result


def test_plan_reminder_short_compact():
    result = plan_reminder(full=False)
    assert "<system-reminder>" in result
    assert "plan-only" in result


def test_should_inject_always_true():
    assert should_inject_plan_reminder(1) is True
    assert should_inject_plan_reminder(5) is True
