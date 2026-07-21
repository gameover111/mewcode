from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

from mewcode.providers import PromptTooLongError
from mewcode.providers.base import ChatRequest, ProviderError, ProviderEvent
from mewcode.providers.sse import iter_sse_data_lines


DEFAULT_MAX_TOKENS = 4096
DEFAULT_THINKING_BUDGET = 1024


class ClaudeProvider:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=None)

    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]:
        payload = self._build_payload(request)
        headers = {
            "x-api-key": request.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "accept": "text/event-stream",
        }

        try:
            with self._client.stream(
                "POST",
                request.config.base_url,
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                yield from self._iter_events(response)
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            error_text = _response_error_detail(exc.response)
            if _is_prompt_too_long(status_code, error_text):
                raise PromptTooLongError(f"Claude API 上下文过长：{error_text}") from exc
            raise ProviderError(f"Claude API 请求失败，HTTP 状态码：{status_code}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Claude API 网络请求失败：{exc}") from exc

    def _build_payload(self, request: ChatRequest) -> dict:
        payload = {
            "model": request.config.model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "stream": True,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
        }
        if request.config.thinking:
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": DEFAULT_THINKING_BUDGET,
                "display": "summarized",
            }
        return payload

    def _iter_events(self, response: httpx.Response) -> Iterator[ProviderEvent]:
        for data_line in iter_sse_data_lines(response):
            try:
                data = json.loads(data_line)
            except json.JSONDecodeError as exc:
                raise ProviderError(f"Claude API 返回了无法解析的流式数据：{data_line}") from exc

            event_type = data.get("type")
            if event_type == "content_block_delta":
                delta = data.get("delta", {})
                delta_type = delta.get("type")
                if delta_type == "text_delta" and delta.get("text"):
                    yield ProviderEvent(type="text", content=str(delta["text"]))
                elif delta_type == "thinking_delta" and delta.get("thinking"):
                    yield ProviderEvent(type="thinking", content=str(delta["thinking"]))
            elif event_type == "error":
                error = data.get("error", {})
                message = error.get("message", "未知错误")
                yield ProviderEvent(type="error", content=f"Claude API 错误：{message}")
            elif event_type == "message_stop":
                yield ProviderEvent(type="done")
                return


def _response_error_detail(response: httpx.Response) -> str:
    text = response.text.strip()
    if not text:
        return "无响应内容"
    try:
        data = response.json()
    except ValueError:
        return text[:1000]
    return json.dumps(data, ensure_ascii=False)[:1000]


def _is_prompt_too_long(status_code: int, error_text: str) -> bool:
    if status_code not in (400, 413):
        return False
    keywords = ["prompt_too_long", "too long", "context", "token", "length"]
    lower = error_text.lower()
    return any(kw in lower for kw in keywords)
