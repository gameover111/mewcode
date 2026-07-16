from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

from mewcode.providers.base import ChatRequest, ProviderError, ProviderEvent
from mewcode.providers.sse import iter_sse_data_lines


class OpenAIProvider:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=None)

    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]:
        payload = {
            "model": request.config.model,
            "stream": True,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
        }
        headers = {
            "authorization": f"Bearer {request.config.api_key}",
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
            raise ProviderError(f"OpenAI API 请求失败，HTTP 状态码：{status_code}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"OpenAI API 网络请求失败：{exc}") from exc

    def _iter_events(self, response: httpx.Response) -> Iterator[ProviderEvent]:
        for data_line in iter_sse_data_lines(response):
            if data_line == "[DONE]":
                yield ProviderEvent(type="done")
                return

            try:
                data = json.loads(data_line)
            except json.JSONDecodeError as exc:
                raise ProviderError(f"OpenAI API 返回了无法解析的流式数据：{data_line}") from exc

            if data.get("error"):
                message = data["error"].get("message", "未知错误")
                yield ProviderEvent(type="error", content=f"OpenAI API 错误：{message}")
                continue

            for choice in data.get("choices", []):
                content = choice.get("delta", {}).get("content")
                if content:
                    yield ProviderEvent(type="text", content=str(content))
