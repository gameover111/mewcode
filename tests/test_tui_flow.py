from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from mewcode.providers.base import (
    ChatRequest,
    ProviderConfig,
    ProviderError,
    ProviderEvent,
    ToolCall,
)
from mewcode.tui import run_chat_loop


class FakeProvider:
    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]:
        self.requests.append(request)
        yield ProviderEvent(type="text", content="你好")
        yield ProviderEvent(type="text", content="，我是 MewCode")
        yield ProviderEvent(type="done")


class ErrorProvider:
    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]:
        raise ProviderError("模拟失败")
        yield ProviderEvent(type="done")


class ToolProvider:
    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]:
        self.requests.append(request)
        if len(self.requests) == 1:
            yield ProviderEvent(
                type="tool_call",
                tool_call=ToolCall(
                    id="call_1",
                    name="read_file",
                    arguments_json='{"path":"README.md"}',
                ),
            )
        else:
            yield ProviderEvent(type="text", content="读完了")
            yield ProviderEvent(type="done")


def make_config() -> ProviderConfig:
    return ProviderConfig(
        name="test-provider",
        protocol="openai",
        model="test-model",
        base_url="https://example.com",
        api_key="test-key",
    )


def run_with_inputs(inputs: list[str], provider):
    output: list[str] = []
    iterator = iter(inputs)

    def fake_input(prompt: str) -> str:
        output.append(prompt)
        return next(iterator)

    exit_code = run_chat_loop(
        make_config(),
        provider,
        input_func=fake_input,
        output_func=output.append,
        workspace=Path.cwd(),
    )
    return exit_code, output


def test_tui_streams_reply_and_exits():
    provider = FakeProvider()

    exit_code, output = run_with_inputs(["你好", "/exit"], provider)

    assert exit_code == 0
    assert "欢迎使用 MewCode，当前配置：test-provider" in output
    assert "MewCode> " in output
    assert "你好" in output
    assert "，我是 MewCode" in output
    assert "已退出 MewCode。" in output


def test_tui_keeps_multi_turn_context():
    provider = FakeProvider()

    run_with_inputs(["第一句", "第二句", "/quit"], provider)

    assert len(provider.requests) == 2
    second_messages = provider.requests[1].messages
    # Agent Loop 的 system prompt 通过 ChatRequest.system 传入，不在 messages 中
    roles = [message.role for message in second_messages]
    # 只有 user/assistant/tool 角色
    assert "user" in roles
    assert "assistant" in roles
    # 找到 user/assistant 消息验证内容
    user_msgs = [m for m in second_messages if m.role == "user"]
    assistant_msgs = [m for m in second_messages if m.role == "assistant"]
    assert user_msgs[0].content == "第一句"
    assert assistant_msgs[0].content == "你好，我是 MewCode"
    assert user_msgs[-1].content == "第二句"

def test_tui_shows_provider_error_and_continues_to_exit():
    exit_code, output = run_with_inputs(["你好", "/exit"], ErrorProvider())

    assert exit_code == 0
    assert "错误：模拟失败" in output
    assert "已退出 MewCode。" in output


def test_tui_shows_tool_status(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    output: list[str] = []
    inputs = iter(["读 README", "/exit"])

    def fake_input(prompt: str) -> str:
        output.append(prompt)
        return next(inputs)

    run_chat_loop(
        make_config(),
        ToolProvider(),
        input_func=fake_input,
        output_func=output.append,
        workspace=tmp_path,
    )

    assert "[工具] 调用工具：read_file" in output
    assert "[工具结果] 已读取文件：README.md" in output
    assert "读完了" in output
