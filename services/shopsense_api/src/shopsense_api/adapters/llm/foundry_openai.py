"""Foundry models through the OpenAI-compatible v1 endpoint.

One adapter serves several vendors deployed on the same Foundry resource (OpenAI GPT,
Meta Llama, ...); each registered instance has its own provider name for routing.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import openai
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
    ParsedChatCompletion,
)
from pydantic import BaseModel, ValidationError

from shopsense_api.adapters.llm.provider import ModelRoute, ProviderError, validation_problems
from shopsense_api.application.ports.llm import StructuredRequest, StructuredResponse, TokenUsage
from shopsense_api.application.ports.tool_llm import (
    ChatMessage,
    ToolCall,
    ToolTurn,
    ToolTurnRequest,
)
from shopsense_api.domain.exceptions import LLMOutputInvalid, LLMRefused

_TRANSIENT = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)


class FoundryOpenAIProvider:
    def __init__(self, name: str, client: AsyncOpenAI) -> None:
        self.name = name
        self._client = client

    async def generate[T: BaseModel](
        self, route: ModelRoute, request: StructuredRequest[T]
    ) -> StructuredResponse[T]:
        with _translated_errors():
            if route.output_mode == "json_object":
                return await self._json_object(route, request)
            return await self._json_schema(route, request)

    async def complete_with_tools(self, route: ModelRoute, request: ToolTurnRequest) -> ToolTurn:
        with _translated_errors():
            completion = await self._client.with_options(
                timeout=route.timeout_s
            ).chat.completions.create(
                model=route.model,
                max_completion_tokens=route.max_tokens,
                messages=_tool_messages(request),
                tools=[_tool_param(t.name, t.description, t.parameters) for t in request.tools],
                tool_choice="auto",
            )
        choice = completion.choices[0]
        if choice.finish_reason == "content_filter":
            raise LLMRefused("content filter stopped the response")
        calls = tuple(
            _tool_call(c)
            for c in choice.message.tool_calls or []
            if isinstance(c, ChatCompletionMessageFunctionToolCall)
        )
        content = choice.message.content or ""
        return ToolTurn(content, calls, self.name, route.model, _usage(completion))

    async def _json_schema[T: BaseModel](
        self, route: ModelRoute, request: StructuredRequest[T]
    ) -> StructuredResponse[T]:
        completion = await self._client.with_options(
            timeout=route.timeout_s
        ).chat.completions.parse(
            model=route.model,
            max_completion_tokens=route.max_tokens,
            messages=_messages(request.system_prompt, request.user_message),
            response_format=request.output_type,
        )
        return self._from_parsed(route, completion)

    async def _json_object[T: BaseModel](
        self, route: ModelRoute, request: StructuredRequest[T]
    ) -> StructuredResponse[T]:
        schema = json.dumps(request.output_type.model_json_schema())
        instruction = "Respond with one JSON object matching this schema:"
        system = f"{request.system_prompt}\n\n{instruction}\n{schema}"
        completion = await self._client.with_options(
            timeout=route.timeout_s
        ).chat.completions.create(
            model=route.model,
            max_completion_tokens=route.max_tokens,
            messages=_messages(system, request.user_message),
            response_format={"type": "json_object"},
        )
        return self._from_json(route, completion, request.output_type)

    def _from_parsed[T: BaseModel](
        self, route: ModelRoute, completion: ParsedChatCompletion[T]
    ) -> StructuredResponse[T]:
        message = completion.choices[0].message
        if message.refusal:
            raise LLMRefused("model declined the request")
        if message.parsed is None:
            raise LLMOutputInvalid(("no structured output returned",))
        return StructuredResponse(message.parsed, self.name, route.model, _usage(completion))

    def _from_json[T: BaseModel](
        self, route: ModelRoute, completion: ChatCompletion, output_type: type[T]
    ) -> StructuredResponse[T]:
        choice = completion.choices[0]
        if choice.finish_reason == "content_filter":
            raise LLMRefused("content filter stopped the response")
        if choice.finish_reason == "length" or not choice.message.content:
            raise LLMOutputInvalid((f"output incomplete (finish_reason={choice.finish_reason})",))
        output = output_type.model_validate_json(choice.message.content)
        return StructuredResponse(output, self.name, route.model, _usage(completion))


def _messages(system: str, user: str) -> list[ChatCompletionMessageParam]:
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


@contextmanager
def _translated_errors() -> Iterator[None]:
    try:
        yield
    except ValidationError as exc:
        raise LLMOutputInvalid(validation_problems(exc)) from None
    except openai.ContentFilterFinishReasonError as exc:
        raise LLMRefused("content filter stopped the response") from exc
    except openai.LengthFinishReasonError:
        raise LLMOutputInvalid(("output incomplete (length limit)",)) from None
    except openai.BadRequestError as exc:
        if exc.code == "content_filter":
            raise LLMRefused("content filter blocked the request") from exc
        raise ProviderError("HTTP 400", transient=False) from exc
    except _TRANSIENT as exc:
        raise ProviderError(type(exc).__name__, transient=True) from exc
    except openai.APIStatusError as exc:
        raise ProviderError(f"HTTP {exc.status_code}", transient=False) from exc


def _tool_param(name: str, description: str, parameters: dict[str, Any]) -> ChatCompletionToolParam:
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": parameters},
    }


def _tool_messages(request: ToolTurnRequest) -> list[ChatCompletionMessageParam]:
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": request.system_prompt}
    ]
    messages.extend(_message(m) for m in request.messages)
    return messages


def _message(message: ChatMessage) -> ChatCompletionMessageParam:
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id or "",
            "content": message.content,
        }
    if message.role == "assistant":
        calls = [
            {
                "id": c.call_id,
                "type": "function",
                "function": {
                    "name": c.name,
                    "arguments": c.raw_arguments or json.dumps(c.arguments),
                },
            }
            for c in message.tool_calls
        ]
        if calls:
            return {"role": "assistant", "content": message.content or None, "tool_calls": calls}  # type: ignore[typeddict-item]
        return {"role": "assistant", "content": message.content}
    return {"role": "user", "content": message.content}


def _tool_call(call: ChatCompletionMessageFunctionToolCall) -> ToolCall:
    raw = call.function.arguments
    try:
        arguments = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}
    return ToolCall(call.id, call.function.name, arguments, raw)


def _usage(completion: ChatCompletion) -> TokenUsage:
    usage = completion.usage
    return TokenUsage(usage.prompt_tokens, usage.completion_tokens) if usage else TokenUsage(0, 0)
