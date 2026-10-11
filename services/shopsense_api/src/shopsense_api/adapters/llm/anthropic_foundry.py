"""Claude on Azure AI Foundry via the Anthropic SDK (structured outputs).

Server-side refusal fallback is not available on Foundry, so a refusal raises
LLMRefused and the ticket fails closed to a human (D12a).
"""

from typing import cast

import anthropic
from anthropic import AsyncAnthropicFoundry, Omit, omit
from anthropic.types import OutputConfigParam
from pydantic import BaseModel, ValidationError

from shopsense_api.adapters.llm.provider import ModelRoute, ProviderError, validation_problems
from shopsense_api.application.ports.llm import StructuredRequest, StructuredResponse, TokenUsage
from shopsense_api.domain.exceptions import LLMOutputInvalid, LLMRefused

_TRANSIENT = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


class AnthropicFoundryProvider:
    name = "claude-foundry"

    def __init__(self, client: AsyncAnthropicFoundry) -> None:
        self._client = client

    async def generate[T: BaseModel](
        self, route: ModelRoute, request: StructuredRequest[T]
    ) -> StructuredResponse[T]:
        try:
            message = await self._client.with_options(timeout=route.timeout_s).messages.parse(
                model=route.model,
                max_tokens=route.max_tokens,
                system=request.system_prompt,
                messages=[{"role": "user", "content": request.user_message}],
                output_format=request.output_type,
                output_config=_output_config(route),
            )
        except ValidationError as exc:
            raise LLMOutputInvalid(validation_problems(exc)) from None
        except _TRANSIENT as exc:
            raise ProviderError(type(exc).__name__, transient=True) from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"HTTP {exc.status_code}", transient=False) from exc
        return self._to_response(route, message)

    def _to_response[T: BaseModel](
        self, route: ModelRoute, message: "anthropic.types.ParsedMessage[T]"
    ) -> StructuredResponse[T]:
        if message.stop_reason == "refusal":
            raise LLMRefused("model declined the request")
        if message.stop_reason == "max_tokens" or message.parsed_output is None:
            raise LLMOutputInvalid((f"output incomplete (stop_reason={message.stop_reason})",))
        usage = TokenUsage(message.usage.input_tokens, message.usage.output_tokens)
        return StructuredResponse(message.parsed_output, self.name, route.model, usage)


def _output_config(route: ModelRoute) -> OutputConfigParam | Omit:
    if route.effort is None:
        return omit
    return cast("OutputConfigParam", {"effort": route.effort})
