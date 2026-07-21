from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import yaml


class PermissionMode(str, Enum):
    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    PLAN = "plan"
    BYPASS_PERMISSIONS = "bypassPermissions"


class PermissionAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PermissionScope(str, Enum):
    ONCE = "once"
    SESSION = "session"
    PERMANENT = "permanent"


class ToolCategory(str, Enum):
    READ = "read"
    WRITE = "write"
    EXEC = "exec"


@dataclass(frozen=True)
class PermissionRule:
    tool: str
    pattern: str
    action: PermissionAction
    source: str = "unknown"

    @property
    def expr(self) -> str:
        return f"{_friendly_tool_name(self.tool)}({self.pattern})"


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str
    action: PermissionAction = PermissionAction.DENY
    matched_rule: PermissionRule | None = None


@dataclass(frozen=True)
class PermissionRequest:
    tool_name: str
    arguments: dict[str, Any]
    workspace: Path
    read_only: bool = False


PermissionCallback = Callable[[PermissionRequest], tuple[bool, PermissionScope]]


# Heuristic hard blacklist. This layer is intentionally not configurable.
DANGEROUS_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\brm\s+-[a-z]*r[a-z]*f[a-z]*\s+(/|~|\$HOME)(\s|$)"),
    re.compile(r"(?i)\brm\s+-[a-z]*f[a-z]*r[a-z]*\s+(/|~|\$HOME)(\s|$)"),
    re.compile(r"(?i)\brm\s+-[a-z]*r[a-z]*f[a-z]*\s+[/\\]\*"),
    re.compile(r"(?i)\bdel\s+/(s|q)\b"),
    re.compile(r"(?i)\brmdir\s+/(s|q)\b"),
    re.compile(r"(?i)\bformat\s+[a-z]:"),
    re.compile(r"(?i)\bdd\b.*\bof=/dev/"),
    re.compile(r"(?i)\bmkfs(\.| )"),
    re.compile(r">\s*/dev/(sd|hd|vd|xvd|nvme|disk)"),
    re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;?\s*:"),
    re.compile(r"(?i)\bshutdown\b"),
    re.compile(r"(?i)\breg\s+delete\b"),
)


def parse_permission_mode(value: PermissionMode | str | None) -> PermissionMode:
    if isinstance(value, PermissionMode):
        return value
    if value is None or str(value).strip() == "":
        return PermissionMode.DEFAULT

    normalized = str(value).strip().replace("-", "").replace("_", "").lower()
    aliases = {
        "default": PermissionMode.DEFAULT,
        "strict": PermissionMode.DEFAULT,
        "acceptedits": PermissionMode.ACCEPT_EDITS,
        "acceptedit": PermissionMode.ACCEPT_EDITS,
        "plan": PermissionMode.PLAN,
        "bypass": PermissionMode.BYPASS_PERMISSIONS,
        "bypasspermissions": PermissionMode.BYPASS_PERMISSIONS,
        "permissive": PermissionMode.BYPASS_PERMISSIONS,
    }
    if normalized not in aliases:
        raise ValueError(f"\u672a\u77e5\u6743\u9650\u6a21\u5f0f\uff1a{value}")
    return aliases[normalized]


def next_permission_mode(mode: PermissionMode) -> PermissionMode:
    order = [
        PermissionMode.DEFAULT,
        PermissionMode.ACCEPT_EDITS,
        PermissionMode.PLAN,
        PermissionMode.BYPASS_PERMISSIONS,
    ]
    return order[(order.index(mode) + 1) % len(order)]


def parse_rule_expr(expr: str, action: str, source: str = "unknown") -> PermissionRule:
    match = re.fullmatch(r"\s*([A-Za-z_][\w]*)(?:\((.*)\))?\s*", expr)
    if not match:
        raise ValueError(f"\u6743\u9650\u89c4\u5219\u683c\u5f0f\u65e0\u6548\uff1a{expr}")

    raw_action = action.strip().lower()
    if raw_action not in {PermissionAction.ALLOW.value, PermissionAction.DENY.value}:
        raise ValueError(
            f"\u6743\u9650\u89c4\u5219\u7ed3\u679c\u5fc5\u987b\u662f allow \u6216 deny\uff1a{action}"
        )

    return PermissionRule(
        tool=_canonical_tool_name(match.group(1)),
        pattern=(match.group(2) or "").strip(),
        action=PermissionAction(raw_action),
        source=source,
    )


def load_rules_file(path: Path, source: str) -> tuple[PermissionMode | None, list[PermissionRule]]:
    try:
        exists = path.exists()
    except OSError:
        return None, []
    if not exists:
        return None, []

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None, []
    if not isinstance(data, dict):
        return None, []

    mode = _mode_from_config(data)
    rules: list[PermissionRule] = []

    raw_rules = data.get("rules") or {}
    if isinstance(raw_rules, dict):
        for expr, action in raw_rules.items():
            try:
                rules.append(parse_rule_expr(str(expr), str(action), source=source))
            except ValueError:
                continue

    permissions = data.get("permissions") or {}
    if isinstance(permissions, dict):
        for action_name in ("allow", "deny"):
            raw_items = permissions.get(action_name) or []
            if isinstance(raw_items, str):
                raw_items = [raw_items]
            if not isinstance(raw_items, list):
                continue
            for expr in raw_items:
                try:
                    rules.append(parse_rule_expr(str(expr), action_name, source=source))
                except ValueError:
                    continue

    return mode, rules


class PermissionManager:
    def __init__(
        self,
        mode: PermissionMode = PermissionMode.DEFAULT,
        user_rules: list[PermissionRule] | None = None,
        project_rules: list[PermissionRule] | None = None,
        local_rules: list[PermissionRule] | None = None,
        session_rules: list[PermissionRule] | None = None,
        callback: PermissionCallback | None = None,
        permanent_rules_path: Path | None = None,
    ) -> None:
        self.mode = parse_permission_mode(mode)
        self.user_rules = user_rules or []
        self.project_rules = project_rules or []
        self.local_rules = local_rules or []
        self.session_rules = session_rules or []
        self.callback = callback
        self.permanent_rules_path = permanent_rules_path

    @classmethod
    def from_files(
        cls,
        workspace: Path,
        user_path: Path | None = None,
        project_path: Path | None = None,
        local_path: Path | None = None,
        callback: PermissionCallback | None = None,
        mode_override: PermissionMode | str | None = None,
    ) -> PermissionManager:
        workspace = workspace.resolve()
        user_path = user_path or (Path.home() / ".mewcode" / "settings.yaml")
        project_path = project_path or (workspace / ".mewcode" / "settings.yaml")
        local_path = local_path or (workspace / ".mewcode" / "settings.local.yaml")

        user_mode, user_rules = _load_first_existing(
            [(user_path, "user"), (Path.home() / ".mewcode" / "permissions.yaml", "user")]
        )
        project_mode, project_rules = _load_first_existing(
            [(project_path, "project"), (workspace / ".mewcode" / "permissions.yaml", "project")]
        )
        local_mode, local_rules = _load_first_existing(
            [(local_path, "local"), (workspace / ".mewcode" / "permissions.local.yaml", "local")]
        )

        mode = PermissionMode.DEFAULT
        for candidate in (user_mode, project_mode, local_mode):
            if candidate is not None:
                mode = candidate
        if mode_override is not None:
            mode = parse_permission_mode(mode_override)

        return cls(
            mode=mode,
            user_rules=user_rules,
            project_rules=project_rules,
            local_rules=local_rules,
            callback=callback,
            permanent_rules_path=local_path,
        )

    def cycle_mode(self) -> PermissionMode:
        self.mode = next_permission_mode(self.mode)
        return self.mode

    def add_session_rule(self, rule: PermissionRule) -> None:
        self.session_rules.insert(0, rule)

    def check(self, request: PermissionRequest) -> PermissionDecision:
        hard = _check_hard_blacklist(request)
        if hard is not None:
            return hard

        sandbox = _check_path_sandbox(request)
        if sandbox is not None:
            return sandbox

        rule_decision = self._check_rules(request)
        if rule_decision is not None:
            return rule_decision

        fallback = _mode_fallback(self.mode, _tool_category(request))
        if fallback == PermissionAction.ALLOW:
            return PermissionDecision(True, "", action=PermissionAction.ALLOW)
        return self._ask_or_deny(request, _ask_reason(self.mode, request))

    def _check_rules(self, request: PermissionRequest) -> PermissionDecision | None:
        for source, rules in (
            ("session", self.session_rules),
            ("local", self.local_rules),
            ("project", self.project_rules),
            ("user", self.user_rules),
        ):
            denied = _first_matching_rule(rules, request, PermissionAction.DENY)
            if denied is not None:
                return PermissionDecision(
                    False,
                    f"\u5339\u914d deny \u89c4\u5219\uff1a{denied.expr}",
                    action=PermissionAction.DENY,
                    matched_rule=denied,
                )
            allowed = _first_matching_rule(rules, request, PermissionAction.ALLOW)
            if allowed is not None:
                return PermissionDecision(
                    True,
                    "",
                    action=PermissionAction.ALLOW,
                    matched_rule=allowed,
                )
        return None

    def _ask_or_deny(self, request: PermissionRequest, reason: str) -> PermissionDecision:
        if self.callback is None:
            return PermissionDecision(
                False,
                f"{reason}\uff1b\u5f53\u524d\u6ca1\u6709\u4eba\u5728\u56de\u8def\u786e\u8ba4\u56de\u8c03\uff0c\u5df2\u62d2\u7edd",
                action=PermissionAction.ASK,
            )

        allowed, scope = self.callback(request)
        if allowed and scope == PermissionScope.SESSION:
            self.add_session_rule(_rule_from_request(request, source="session"))
        elif allowed and scope == PermissionScope.PERMANENT:
            rule = _rule_from_request(request, source="local")
            self.add_session_rule(rule)
            self._save_permanent_rule(rule)

        return PermissionDecision(
            allowed,
            f"{reason}\uff1b\u4eba\u5728\u56de\u8def\u7ed3\u679c\uff1a{scope.value}",
            action=PermissionAction.ALLOW if allowed else PermissionAction.DENY,
        )

    def _save_permanent_rule(self, rule: PermissionRule) -> None:
        if self.permanent_rules_path is None:
            return

        path = self.permanent_rules_path
        path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        if path.exists():
            try:
                loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                loaded = {}
            if isinstance(loaded, dict):
                data = loaded

        permissions = data.setdefault("permissions", {})
        if not isinstance(permissions, dict):
            permissions = {}
            data["permissions"] = permissions
        allow_rules = permissions.setdefault("allow", [])
        if not isinstance(allow_rules, list):
            allow_rules = []
            permissions["allow"] = allow_rules

        expr = rule.expr
        if expr not in allow_rules:
            allow_rules.append(expr)
        if all(existing.expr != rule.expr for existing in self.local_rules):
            self.local_rules.append(rule)

        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


def _load_first_existing(paths: list[tuple[Path, str]]) -> tuple[PermissionMode | None, list[PermissionRule]]:
    for path, source in paths:
        try:
            if path.exists():
                return load_rules_file(path, source)
        except OSError:
            continue
    return None, []


def _mode_from_config(data: dict[str, Any]) -> PermissionMode | None:
    raw = data.get("default_mode", data.get("defaultMode", data.get("mode")))
    if raw is None:
        return None
    try:
        return parse_permission_mode(str(raw))
    except ValueError:
        return None


def _canonical_tool_name(name: str) -> str:
    aliases = {
        "Bash": "run_command",
        "Read": "read_file",
        "Write": "write_file",
        "Edit": "replace_in_file",
        "Glob": "find_files",
        "Grep": "search_code",
    }
    return aliases.get(name, name)


def _friendly_tool_name(name: str) -> str:
    aliases = {
        "run_command": "Bash",
        "read_file": "Read",
        "write_file": "Write",
        "replace_in_file": "Edit",
        "find_files": "Glob",
        "search_code": "Grep",
    }
    return aliases.get(name, name)


def _tool_category(request: PermissionRequest) -> ToolCategory:
    if request.read_only:
        return ToolCategory.READ
    tool_name = request.tool_name
    if tool_name in {"read_file", "find_files", "search_code"}:
        return ToolCategory.READ
    if tool_name in {"write_file", "replace_in_file"}:
        return ToolCategory.WRITE
    return ToolCategory.EXEC


def _mode_fallback(mode: PermissionMode, category: ToolCategory) -> PermissionAction:
    if category == ToolCategory.READ:
        return PermissionAction.ALLOW
    if mode == PermissionMode.BYPASS_PERMISSIONS:
        return PermissionAction.ALLOW
    if mode == PermissionMode.ACCEPT_EDITS and category == ToolCategory.WRITE:
        return PermissionAction.ALLOW
    return PermissionAction.ASK


def _ask_reason(mode: PermissionMode, request: PermissionRequest) -> str:
    category = _tool_category(request).value
    return f"{mode.value} \u6a21\u5f0f\u4e0b {category} \u7c7b\u64cd\u4f5c\u9700\u786e\u8ba4"


def _check_hard_blacklist(request: PermissionRequest) -> PermissionDecision | None:
    if request.tool_name != "run_command":
        return None

    command = str(request.arguments.get("command") or "")
    for pattern in DANGEROUS_COMMAND_PATTERNS:
        if pattern.search(command):
            return PermissionDecision(
                False,
                f"\u547d\u4e2d\u5371\u9669\u547d\u4ee4\u9ed1\u540d\u5355\uff1a{pattern.pattern}",
                action=PermissionAction.DENY,
            )
    return None


def _check_path_sandbox(request: PermissionRequest) -> PermissionDecision | None:
    if request.tool_name == "run_command":
        return None

    workspace = request.workspace.resolve()
    for field in _path_fields_for_tool(request.tool_name):
        value = request.arguments.get(field)
        if not isinstance(value, str) or value == "":
            return PermissionDecision(
                False,
                "\u65e0\u6cd5\u89e3\u6790\u6587\u4ef6\u8def\u5f84\u53c2\u6570\uff0c\u5b89\u5168\u62d2\u7edd",
                action=PermissionAction.DENY,
            )

        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = workspace / candidate
        resolved = _resolve_existing_ancestor(candidate)
        try:
            resolved.relative_to(workspace)
        except ValueError:
            return PermissionDecision(
                False,
                f"\u8def\u5f84\u5728\u9879\u76ee\u76ee\u5f55\u4e4b\u5916\uff1a{value}",
                action=PermissionAction.DENY,
            )
    return None


def _resolve_existing_ancestor(path: Path) -> Path:
    missing: list[str] = []
    current = path
    while not current.exists() and current != current.parent:
        missing.append(current.name)
        current = current.parent
    resolved = current.resolve(strict=True)
    for part in reversed(missing):
        resolved = resolved / part
    return resolved


def _path_fields_for_tool(tool_name: str) -> tuple[str, ...]:
    if tool_name in {"read_file", "write_file", "replace_in_file"}:
        return ("path",)
    return ()


def _first_matching_rule(
    rules: list[PermissionRule],
    request: PermissionRequest,
    action: PermissionAction,
) -> PermissionRule | None:
    for rule in rules:
        if rule.action == action and _matches_rule(rule, request):
            return rule
    return None


def _matches_rule(rule: PermissionRule, request: PermissionRequest) -> bool:
    if rule.tool != request.tool_name:
        return False
    if rule.pattern == "":
        return True
    target = _target_for_request(request)
    return target == rule.pattern or fnmatch.fnmatchcase(target, rule.pattern)


def _rule_from_request(request: PermissionRequest, source: str) -> PermissionRule:
    return PermissionRule(
        tool=request.tool_name,
        pattern=_target_for_request(request),
        action=PermissionAction.ALLOW,
        source=source,
    )


def _target_for_request(request: PermissionRequest) -> str:
    if request.tool_name == "run_command":
        return str(request.arguments.get("command") or "")
    if request.tool_name in {"read_file", "write_file", "replace_in_file"}:
        return _normalize_rule_path(str(request.arguments.get("path") or ""))
    if request.tool_name == "find_files":
        return str(request.arguments.get("pattern") or "")
    if request.tool_name == "search_code":
        return str(request.arguments.get("query") or request.arguments.get("pattern") or "")
    return ""


def _normalize_rule_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")
