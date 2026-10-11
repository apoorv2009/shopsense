"""Azure OpenAI model on Foundry (second provider for the provider-agnostic client)."""

import openai
from openai import AsyncAzureOpenAI
from openai.types.chat import ParsedChatCompletion
from pydantic import BaseModel, ValidationError

from shopsense_api.adapters.llm.provider import ModelRoute, ProviderError, validation_problems
from shopsense_api.application.ports.llm import StructuredRequest, StructuredResponse, TokenUsage
from shopsense_api.domain.exceptions import LLMOutputInvalid, LLMRefused

_TRANSIENT = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)


class AzureOpenAIProvider:
    name = "azure-openai"

    def __init__(self, client: AsyncAzureOpenAI) -> None:
        self._client = client

    async def generate[T: BaseModel](
        self, route: ModelRoute, request: StructuredRequest[T]
    ) -> StructuredResponse[T]:
        try:
            completion = await self._client.with_options(
                timeout=route.timeout_s
            ).chat.completions.parse(
                model=route.model,
                max_completion_tokens=route.max_tokens,
                messages=[
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_message},
                ],
                response_format=request.output_type,
            )
        except ValidationError as exc:
            raise LLMOutputInvalid(validation_problems(exc)) from None
        except openai.ContentFilterFinishReasonError as exc:
            raise LLMRefused("content filter stopped the response") from exc
        except openai.LengthFinishReasonError:
            raise LLMOutputInvalid(("output incomplete (length limit)",)) from None
        except _TRANSIENT as exc:
            raise ProviderError(type(exc).__name__, transient=True) from exc
        except openai.APIStatusError as exc:
            raise ProviderError(f"HTTP {exc.status_code}", transient=False) from exc
        return self._to_response(route, completion)

    def _to_response[T: BaseModel](
        self, route: ModelRoute, completion: ParsedChatCompletion[T]
    ) -> StructuredResponse[T]:
        message = completion.choices[0].message
        if message.refusal:
            raise LLMRefused("model declined the request")
        if message.parsed is None:
            raise LLMOutputInvalid(("no structured output returned",))
        usage = completion.usage
        tokens = (
            TokenUsage(usage.prompt_tokens, usage.completion_tokens) if usage else TokenUsage(0, 0)
        )
        return StructuredResponse(message.parsed, self.name, route.model, tokens)
