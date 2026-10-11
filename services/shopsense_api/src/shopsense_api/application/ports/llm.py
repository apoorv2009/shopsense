"""LLM port. Use cases name an agent profile, never a model or provider; the
gateway adapter resolves profiles to providers, models and effort."""

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class StructuredRequest[T: BaseModel]:
    profile: str
    system_prompt: str
    user_message: str
    output_type: type[T]


@dataclass(frozen=True, slots=True)
class StructuredResponse[T: BaseModel]:
    output: T
    provider: str
    model: str
    usage: TokenUsage


class LLMClient(Protocol):
    async def generate_structured[T: BaseModel](
        self, request: StructuredRequest[T]
    ) -> StructuredResponse[T]:
        """Return output validated against request.output_type.

        Raises LLMOutputInvalid, LLMRefused or LLMUnavailable.
        """
        ...
