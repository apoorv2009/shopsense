"""Test doubles for application ports."""

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from shopsense_api.application.ports.llm import StructuredRequest, StructuredResponse, TokenUsage
from shopsense_api.application.ports.prompts import PromptTemplate
from shopsense_api.domain.ticket.support_ticket import SupportTicket


class ScriptedLLM:
    """Returns (or raises) the scripted outcomes in order and records every request."""

    def __init__(self, outcomes: Sequence[BaseModel | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[StructuredRequest[Any]] = []

    async def generate_structured[T: BaseModel](
        self, request: StructuredRequest[T]
    ) -> StructuredResponse[T]:
        self.requests.append(request)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, request.output_type)
        return StructuredResponse(outcome, "fake", "fake-model", TokenUsage(10, 5))


class StaticPrompts:
    def get(self, name: str) -> PromptTemplate:
        return PromptTemplate(name=name, version="v-test", text=f"system prompt for {name}")


def make_ticket(**overrides: Any) -> SupportTicket:
    fields: dict[str, Any] = {
        "issue_type": "refund_request",
        "secondary_issues": [],
        "order_id": "ORD-100003",
        "product_category_hint": "electronics",
        "claimed_amount_paise": 5_499_000,
        "sentiment": "angry",
        "urgency": "high",
        "flags": [],
        "language": "en",
        "summary": "Customer wants a refund for a laptop that does not boot.",
    }
    return SupportTicket.model_validate(fields | overrides)
