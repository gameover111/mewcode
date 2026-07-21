from __future__ import annotations

import os
from pathlib import Path

import pytest

from mewcode.permissions import (
    PermissionAction,
    PermissionManager,
    PermissionMode,
    PermissionRequest,
    PermissionRule,
    PermissionScope,
    parse_permission_mode,
    parse_rule_expr,
)


def req(tool_name: str, arguments: dict, workspace: Path) -> PermissionRequest:
    return PermissionRequest(tool_name=tool_name, arguments=arguments, workspace=workspace)


def test_parse_mode_and_rule_aliases():
    assert parse_permission_mode("acceptEdits") == PermissionMode.ACCEPT_EDITS
    assert parse_permission_mode("bypassPermissions") == PermissionMode.BYPASS_PERMISSIONS

    rule = parse_rule_expr("Bash(git *)", "allow", source="test")

    assert rule.tool == "run_command"
    assert rule.pattern == "git *"
    assert rule.action == PermissionAction.ALLOW
    assert rule.expr == "Bash(git *)"


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "rm -fr ~",
        ":(){ :|:& };:",
        "dd if=/dev/zero of=/dev/sda",
        "mkfs.ext4 /dev/sda1",
    ],
)
def test_blacklist_denies_even_in_bypass(command: str, tmp_path: Path):
    manager = PermissionManager(mode=PermissionMode.BYPASS_PERMISSIONS)

    decision = manager.check(req("run_command", {"command": command}, tmp_path))

    assert decision.allowed is False
    assert decision.action == PermissionAction.DENY
    assert "\u9ed1\u540d\u5355" in decision.reason


def test_sandbox_denies_external_paths_and_allows_internal_new_file(tmp_path: Path):
    manager = PermissionManager(mode=PermissionMode.BYPASS_PERMISSIONS)

    outside = manager.check(req("read_file", {"path": "../outside.txt"}, tmp_path))
    inside_new = manager.check(
        req("write_file", {"path": "new/deep/file.txt"}, tmp_path)
    )

    assert outside.allowed is False
    assert "\u9879\u76ee\u76ee\u5f55\u4e4b\u5916" in outside.reason
    assert inside_new.allowed is True


def test_sandbox_denies_symlink_escape(tmp_path: Path):
    outside_dir = tmp_path.parent / f"{tmp_path.name}_outside"
    outside_dir.mkdir(exist_ok=True)
    link = tmp_path / "link"
    try:
        os.symlink(outside_dir, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"当前环境不支持创建符号链接：{exc}")

    manager = PermissionManager(mode=PermissionMode.BYPASS_PERMISSIONS)
    decision = manager.check(req("read_file", {"path": "link/secret.txt"}, tmp_path))

    assert decision.allowed is False


def test_exact_and_glob_rules(tmp_path: Path):
    exact = PermissionManager(
        mode=PermissionMode.DEFAULT,
        local_rules=[
            PermissionRule("run_command", "git status", PermissionAction.ALLOW, "local")
        ],
    )
    glob = PermissionManager(
        mode=PermissionMode.DEFAULT,
        local_rules=[
            PermissionRule("run_command", "git *", PermissionAction.ALLOW, "local"),
            PermissionRule("write_file", "src/**", PermissionAction.ALLOW, "local"),
        ],
    )

    assert exact.check(req("run_command", {"command": "git status"}, tmp_path)).allowed
    assert not exact.check(req("run_command", {"command": "git push"}, tmp_path)).allowed
    assert glob.check(req("run_command", {"command": "git push"}, tmp_path)).allowed
    assert glob.check(req("write_file", {"path": "src/a/b.py"}, tmp_path)).allowed
    assert not glob.check(req("write_file", {"path": "docs/x"}, tmp_path)).allowed


def test_deny_rule_and_same_layer_deny_priority(tmp_path: Path):
    manager = PermissionManager(
        mode=PermissionMode.BYPASS_PERMISSIONS,
        local_rules=[
            PermissionRule("run_command", "git *", PermissionAction.ALLOW, "local"),
            PermissionRule("run_command", "git push", PermissionAction.DENY, "local"),
        ],
    )

    decision = manager.check(req("run_command", {"command": "git push"}, tmp_path))

    assert decision.allowed is False
    assert decision.matched_rule is not None
    assert decision.matched_rule.action == PermissionAction.DENY


def test_layer_priority_local_project_user(tmp_path: Path):
    manager = PermissionManager(
        mode=PermissionMode.DEFAULT,
        user_rules=[
            PermissionRule("run_command", "git *", PermissionAction.ALLOW, "user")
        ],
        project_rules=[
            PermissionRule("run_command", "git *", PermissionAction.ALLOW, "project")
        ],
        local_rules=[
            PermissionRule("run_command", "git *", PermissionAction.DENY, "local")
        ],
    )

    decision = manager.check(req("run_command", {"command": "git status"}, tmp_path))

    assert decision.allowed is False
    assert decision.matched_rule is not None
    assert decision.matched_rule.source == "local"


@pytest.mark.parametrize(
    ("mode", "tool", "expected_allowed"),
    [
        (PermissionMode.DEFAULT, "read_file", True),
        (PermissionMode.DEFAULT, "write_file", False),
        (PermissionMode.DEFAULT, "run_command", False),
        (PermissionMode.ACCEPT_EDITS, "write_file", True),
        (PermissionMode.ACCEPT_EDITS, "run_command", False),
        (PermissionMode.PLAN, "write_file", False),
        (PermissionMode.PLAN, "run_command", False),
        (PermissionMode.BYPASS_PERMISSIONS, "write_file", True),
        (PermissionMode.BYPASS_PERMISSIONS, "run_command", True),
    ],
)
def test_mode_matrix(mode: PermissionMode, tool: str, expected_allowed: bool, tmp_path: Path):
    args = {"path": "file.txt"} if tool != "run_command" else {"command": "echo ok"}
    manager = PermissionManager(mode=mode)

    decision = manager.check(req(tool, args, tmp_path))

    assert decision.allowed is expected_allowed


def test_safe_defaults_for_unknown_tool_and_bad_file_args(tmp_path: Path):
    manager = PermissionManager(mode=PermissionMode.DEFAULT)

    unknown = manager.check(req("unknown_tool", {}, tmp_path))
    missing_path = manager.check(req("write_file", {}, tmp_path))

    assert unknown.allowed is False
    assert missing_path.allowed is False


def test_config_degrades_and_default_mode_priority(tmp_path: Path):
    user = tmp_path / "user.yaml"
    project = tmp_path / "project.yaml"
    local = tmp_path / "local.yaml"
    user.write_text("default_mode: default\n", encoding="utf-8")
    project.write_text("default_mode: acceptEdits\n", encoding="utf-8")
    local.write_text("default_mode: plan\npermissions: [bad\n", encoding="utf-8")

    manager = PermissionManager.from_files(
        tmp_path,
        user_path=user,
        project_path=project,
        local_path=local,
    )

    assert manager.mode == PermissionMode.ACCEPT_EDITS


def test_permanent_allow_persists_and_reloads(tmp_path: Path):
    local = tmp_path / ".mewcode" / "settings.local.yaml"
    manager = PermissionManager(
        mode=PermissionMode.DEFAULT,
        permanent_rules_path=local,
        callback=lambda _request: (True, PermissionScope.PERMANENT),
    )

    decision = manager.check(req("write_file", {"path": "src/a.py"}, tmp_path))
    reloaded = PermissionManager.from_files(tmp_path)

    assert decision.allowed is True
    assert local.exists()
    assert "Write(src/a.py)" in local.read_text(encoding="utf-8")
    assert reloaded.check(req("write_file", {"path": "src/a.py"}, tmp_path)).allowed
