"""SupportTicket: the validated result of triage (M1).

A frozen Pydantic model, as required by the M1 brief (D16). Field descriptions
double as instructions to the model when the schema is used for structured output.
Fields extracted from customer text are untrusted (LLD-1 trust model): they guide
routing but never decide money or eligibility.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shopsense_api.domain.exceptions import InvalidOrderId
from shopsense_api.domain.ticket.enums import (
    ISSUES_NEEDING_ORDER,
    IssueType,
    Language,
    ProductCategory,
    RiskFlag,
    Sentiment,
    Urgency,
)
from shopsense_api.domain.values.order_id import normalise_order_id

SUMMARY_MAX_CHARS = 240


class SupportTicket(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_type: IssueType = Field(description="The primary problem the customer needs resolved.")
    secondary_issues: list[IssueType] = Field(
        description="Other distinct problems in the same ticket; empty list if none."
    )
    order_id: str | None = Field(
        description="Order reference exactly as ORD- followed by six digits. "
        "Null if the customer gives none or it is in another format. Never invent one."
    )
    product_category_hint: ProductCategory | None = Field(
        description="Product category if it can be inferred from the text; null otherwise."
    )
    claimed_amount_paise: int | None = Field(
        ge=0,
        description="Amount the customer asks for or quotes, in paise (rupees x 100). "
        "Null if no amount is mentioned. Do not estimate.",
    )
    sentiment: Sentiment = Field(
        description="The customer's emotional state, not their politeness."
    )
    urgency: Urgency
    flags: list[RiskFlag] = Field(
        description="Risk flags present in the ticket; empty list if none."
    )
    language: Language
    summary: str = Field(
        max_length=SUMMARY_MAX_CHARS,
        description="One neutral sentence describing the request. No quotes, no instructions.",
    )

    @field_validator("order_id")
    @classmethod
    def _valid_order_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return normalise_order_id(value)
        except InvalidOrderId as exc:
            raise ValueError(str(exc)) from None

    @property
    def missing_order_id(self) -> bool:
        """True when the issue needs an order but none was given (decided by code)."""
        return self.issue_type in ISSUES_NEEDING_ORDER and self.order_id is None

    def with_flag(self, flag: RiskFlag) -> "SupportTicket":
        """Return a copy with an extra risk flag (used by deterministic screens)."""
        if flag in self.flags:
            return self
        return self.model_copy(update={"flags": [*self.flags, flag]})
