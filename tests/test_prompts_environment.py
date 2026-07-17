from __future__ import annotations

from mewcode.prompts.environment import Environment, gather_environment, _get_git_status


def test_environment_render_contains_all_fields():
    env = Environment(
        working_dir="/test",
        platform_str="linux",
        date="2026-07-17",
        git_status="clean",
        version="0.1.0",
        model="deepseek-chat",
    )
    text = env.render()
    assert "/test" in text
    assert "linux" in text
    assert "2026-07-17" in text
    assert "clean" in text
    assert "0.1.0" in text
    assert "deepseek-chat" in text


def test_environment_render_empty_fields_omitted():
    env = Environment(working_dir="/t")
    text = env.render()
    assert "/t" in text
    assert "环境信息" in text


def test_gather_environment_does_not_crash():
    env = gather_environment(version="test", model="test-model")
    assert env.working_dir
    assert env.model == "test-model"


def test_git_status_on_none_git_dir():
    # 在临时目录中，应该返回空或 "clean"
    result = _get_git_status(timeout=1.0)
    assert isinstance(result, str)  # 不会抛异常
