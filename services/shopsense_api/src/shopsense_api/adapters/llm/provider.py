"""Adapter-internal contract between the LLM gateway and each model provider."""

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ValidationError

from shopsense_api.application.ports.llm import StructuredRequest, StructuredResponse


@dataclass(frozen=True, slots=True)
class ModelRoute:
    """One provider/model choice for an agent profile."""

    provider: str
    model: str
    max_tokens: int
    timeout_s: float
    effort: str | None = None
    # "json_schema": provider-enforced schema; "json_object": JSON mode + schema in prompt,
    # validated by Pydantic (for models without schema-constrained decoding)
    output_mode: str = "json_schema"


class ProviderError(Exception):
    """Raised by provider adapters. Transient errors let the gateway try the next route."""

    def __init__(self, message: str, *, transient: bool) -> None:
        super().__init__(message)
        self.transient = transient


class ModelProvider(Protocol):
    name: str

    async def generate[T: BaseModel](
        self, route: ModelRoute, request: StructuredRequest[T]
    ) -> StructuredResponse[T]:
        """Raise ProviderError, LLMRefused or LLMOutputInvalid on failure."""
        ...


def validation_problems(error: ValidationError) -> tuple[str, ...]:
    """Summarise a ValidationError without echoing the (untrusted) input values."""
    return tuple(
        f"{'.'.join(str(part) for part in err['loc']) or 'output'}: {err['msg']}"
        for err in error.errors(include_input=False, include_url=False)
    )
