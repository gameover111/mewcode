from __future__ import annotations

from pathlib import Path

from mewcode.agent import execute_tool_calls
from mewcode.permissions import PermissionDecision, PermissionRequest
from mewcode.providers.base import ToolCall
from mewcode.tools.base import ToolContext
from mewcode.tools.registry import create_default_registry


class DenyPermissionManager:
    def __init__(self) -> None:
        self.requests: list[PermissionRequest] = []

    def check(self, request: PermissionRequest) -> PermissionDecision:
        self.requests.append(request)
        return PermissionDecision(False, "\u6d4b\u8bd5\u62d2\u7edd")


def test_agent_returns_structured_permission_denied_result(tmp_path: Path):
    manager = DenyPermissionManager()
    context = ToolContext(workspace=tmp_path, permission_manager=manager)

    results = execute_tool_calls(
        [ToolCall(id="c1", name="read_file", arguments_json='{"path":"README.md"}')],
        create_default_registry(),
        context,
    )

    _, result = results[0]
    assert result.ok is False
    assert result.summary == "\u6743\u9650\u62d2\u7edd\uff1aread_file"
    assert result.data["permission_denied"] is True
    assert result.error == "\u6d4b\u8bd5\u62d2\u7edd"
    assert manager.requests[0].tool_name == "read_file"


def test_mixed_allowed_and_denied_results_keep_order(tmp_path: Path):
    (tmp_path / "ok.txt").write_text("ok", encoding="utf-8")
    context = ToolContext(workspace=tmp_path)

    results = execute_tool_calls(
        [
            ToolCall(id="c1", name="read_file", arguments_json='{"path":"../nope.txt"}'),
            ToolCall(id="c2", name="read_file", arguments_json='{"path":"ok.txt"}'),
        ],
        create_default_registry(),
        context,
    )

    assert [call.id for call, _result in results] == ["c1", "c2"]
    assert results[0][1].ok is False
    assert results[1][1].ok is True
