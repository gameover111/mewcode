from __future__ import annotations

from mewcode.prompts.modules import (
    Module,
    fixed_modules,
    optional_modules,
    assemble_system,
    build_system_prompt,
)


def test_has_seven_fixed_modules():
    mods = fixed_modules()
    assert len(mods) == 7


def test_priorities_are_sequential():
    mods = fixed_modules()
    for i, m in enumerate(mods):
        assert m.priority == (i + 1) * 10


def test_empty_optional_skipped():
    opt = optional_modules()
    assert all(m.content == "" for m in opt)
    result = assemble_system(fixed_modules() + opt)
    # 应该和只用 fixed 一样
    expected = assemble_system(fixed_modules())
    assert result == expected


def test_no_double_newlines_with_empty():
    mods = [
        Module(name="A", priority=10, content="A"),
        Module(name="B", priority=20, content=""),
        Module(name="C", priority=30, content="C"),
    ]
    result = assemble_system(mods)
    assert "A\n\nC" == result
    assert "\n\n\n" not in result


def test_assemble_order_by_priority():
    mods = [
        Module(name="B", priority=50, content="B"),
        Module(name="A", priority=10, content="A"),
        Module(name="C", priority=30, content="C"),
    ]
    result = assemble_system(mods)
    assert result == "A\n\nC\n\nB"


def test_build_system_prompt_is_deterministic():
    a = build_system_prompt()
    b = build_system_prompt()
    assert a == b


def test_tool_module_has_enhanced_rules():
    prompt = build_system_prompt()
    assert "read_file" in prompt
    assert "run_command" in prompt
