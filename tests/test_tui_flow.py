from __future__ import annotations

from collections.abc import Iterator

from mewcode.providers.base import (
    ChatRequest,
    ProviderConfig,
    ProviderError,
    ProviderEvent,
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
    assert [message.role for message in second_messages] == [
        "user",
        "assistant",
        "user",
    ]
    assert second_messages[0].content == "第一句"
    assert second_messages[1].content == "你好，我是 MewCode"
    assert second_messages[2].content == "第二句"


def test_tui_shows_provider_error_and_continues_to_exit():
    exit_code, output = run_with_inputs(["你好", "/exit"], ErrorProvider())

    assert exit_code == 0
    assert "错误：模拟失败" in output
    assert "已退出 MewCode。" in output
