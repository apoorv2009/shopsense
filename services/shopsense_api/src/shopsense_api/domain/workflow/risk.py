"""Risk gate (M5): deterministic routing of a ticket to reply, auto-execution, human approval
or hand-off. Pure code; no model output can change the route (D10, LLD-5).

Routes:
- REPLY: nothing to execute (no refund asked, not eligible, nothing refundable)
- AUTO: a refund within the auto-approval cap, for a calm customer, with no risk flag
- APPROVAL: pause for a reviewer before any write (above the cap, angry or critical customer)
- HUMAN: a risk flag or an evidence/escalation requirement; no write at all
"""

from dataclasses import dataclass
from enum import StrEnum

from shopsense_api.domain.policy.rules_engine import Eligibility
from shopsense_api.domain.ticket.enums import IssueType, RiskFlag, Sentiment, Urgency
from shopsense_api.domain.ticket.support_ticket import SupportTicket

AUTO_CAP_PAISE = 500_000
EMAIL_CHANNEL = "email"
REFUND_ISSUES = frozenset(
    {
        IssueType.REFUND_REQUEST,
        IssueType.RETURN_REQUEST,
        IssueType.DAMAGED_OR_DEFECTIVE,
        IssueType.WRONG_ITEM,
        IssueType.MISSING_ITEM,
    }
)
HUMAN_FLAGS = frozenset(
    {RiskFlag.PROMPT_INJECTION_SUSPECTED, RiskFlag.PRODUCT_SAFETY, RiskFlag.LEGAL_THREAT}
)


class Route(StrEnum):
    REPLY = "reply"
    AUTO = "auto"
    APPROVAL = "approval"
    HUMAN = "human"


@dataclass(frozen=True, slots=True)
class RiskVerdict:
    route: Route
    reasons: tuple[str, ...]


def assess(
    ticket: SupportTicket, eligibility: Eligibility, amount_paise: int, channel: str = "chat"
) -> RiskVerdict:
    if HUMAN_FLAGS & set(ticket.flags):
        return RiskVerdict(Route.HUMAN, ("risk flag needs a specialist",))
    if ticket.issue_type not in REFUND_ISSUES:
        return RiskVerdict(Route.REPLY, ("no refund requested",))
    if eligibility in (Eligibility.NEEDS_EVIDENCE, Eligibility.ESCALATE):
        # The reviewer decides these: checks evidence or escalates, then approves or rejects
        return RiskVerdict(Route.APPROVAL, (f"policy result: {eligibility.value}",))
    if eligibility is Eligibility.NOT_ELIGIBLE or amount_paise <= 0:
        return RiskVerdict(Route.REPLY, ("not refundable under policy",))
    reasons = list(_approval_reasons(ticket, amount_paise))
    if channel == EMAIL_CHANNEL:
        # M6: a refund requested by email is always reviewed, whatever its amount (D8d)
        reasons.append("refund requested by email")
    if reasons:
        return RiskVerdict(Route.APPROVAL, tuple(reasons))
    return RiskVerdict(Route.AUTO, ())


def _approval_reasons(ticket: SupportTicket, amount_paise: int) -> tuple[str, ...]:
    reasons = []
    if amount_paise > AUTO_CAP_PAISE:
        reasons.append("amount above the auto-approval cap")
    if ticket.sentiment is Sentiment.ANGRY:
        reasons.append("customer is angry")
    if ticket.urgency is Urgency.CRITICAL:
        reasons.append("critical urgency")
    return tuple(reasons)
