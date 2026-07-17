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
        # 构建 payload：system + messages + tools
        payload: dict = {}
        payload["model"] = request.config.model
        payload["stream"] = True
        
        # system prompt：stable + environment 合为单条 system 消息
        system_text = ""
        if request.system:
            if request.system.stable:
                system_text = request.system.stable
            if request.system.environment:
                if system_text:
                    system_text += "\n\n"
                system_text += request.system.environment
        if system_text:
            payload["messages"] = [{"role": "system", "content": system_text}]
        else:
            payload["messages"] = []
        
        # 对话历史
        for msg in request.messages:
            payload["messages"].append(_to_openai_message(msg))
        
        # reminder 追加为尾部 user 消息
        if request.reminder:
            payload["messages"].append({"role": "user", "content": request.reminder})
        
        if request.tools:
            payload["tools"] = request.tools
            if request.tool_choice:
                payload["tool_choice"] = request.tool_choice
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
                if response.is_error:
                    response.read()
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

            # 解析用量（含缓存字段）
            usage_data = data.get("usage")
            if usage_data:
                prompt_details = usage_data.get("prompt_tokens_details") or {}
                cached_tokens = 0
                if isinstance(prompt_details, dict):
                    cached_tokens = prompt_details.get("cached_tokens", 0) or 0
                from mewcode.providers.base import Usage as _Usage
                yield ProviderEvent(type="done", usage=_Usage(
                    input_tokens=usage_data.get("prompt_tokens", 0) or 0,
                    output_tokens=usage_data.get("completion_tokens", 0) or 0,
                    cache_read=cached_tokens,
                ))
            
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
