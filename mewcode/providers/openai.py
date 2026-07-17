from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

from mewcode.providers.base import ChatMessage, ChatRequest, ProviderError, ProviderEvent, ToolCall
from mewcode.providers.sse import iter_sse_data_lines


class OpenAIProvider:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=None)

    def stream_chat(self, request: ChatRequest) -> Iterator[ProviderEvent]:
        payload = {
            "model": request.config.model,
            "stream": True,
            "messages": [_to_openai_message(message) for message in request.messages],
        }
        if request.tools:
            payload["tools"] = request.tools
            if request.tool_choice is not None:
                payload["tool_choice"] = request.tool_choice
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
            detail = _response_error_detail(exc.response)
            raise ProviderError(
                f"OpenAI API 请求失败，HTTP 状态码：{status_code}，响应：{detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"OpenAI API 网络请求失败：{exc}") from exc

    def _iter_events(self, response: httpx.Response) -> Iterator[ProviderEvent]:
        tool_call_parts: dict[int, dict[str, str]] = {}
        for data_line in iter_sse_data_lines(response):
            if data_line == "[DONE]":
                yield from _flush_tool_calls(tool_call_parts)
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
                for tool_delta in choice.get("delta", {}).get("tool_calls", []) or []:
                    index = int(tool_delta.get("index", 0))
                    part = tool_call_parts.setdefault(
                        index, {"id": "", "name": "", "arguments": ""}
                    )
                    if tool_delta.get("id"):
                        part["id"] += str(tool_delta["id"])
                    function = tool_delta.get("function") or {}
                    if function.get("name"):
                        part["name"] += str(function["name"])
                    if function.get("arguments"):
                        part["arguments"] += str(function["arguments"])

                if choice.get("finish_reason") == "tool_calls":
                    yield from _flush_tool_calls(tool_call_parts)
                    tool_call_parts.clear()

                content = choice.get("delta", {}).get("content")
                if content:
                    yield ProviderEvent(type="text", content=str(content))


def _to_openai_message(message: ChatMessage) -> dict:
    data: dict = {"role": message.role, "content": message.content}
    if message.tool_call_id:
        data["tool_call_id"] = message.tool_call_id
    if message.tool_calls:
        data["content"] = None
        data["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": tool_call.arguments_json,
                },
            }
            for tool_call in message.tool_calls
        ]
    return data


def _response_error_detail(response: httpx.Response) -> str:
    text = response.text.strip()
    if not text:
        return "无响应内容"
    try:
        data = response.json()
    except ValueError:
        return text[:1000]
    return json.dumps(data, ensure_ascii=False)[:1000]


def _flush_tool_calls(tool_call_parts: dict[int, dict[str, str]]) -> Iterator[ProviderEvent]:
    for index in sorted(tool_call_parts):
        part = tool_call_parts[index]
        if not part["name"]:
            continue
        tool_call_id = part["id"] or f"tool_call_{index}"
        yield ProviderEvent(
            type="tool_call",
            tool_call=ToolCall(
                id=tool_call_id,
                name=part["name"],
                arguments_json=part["arguments"],
            ),
        )
