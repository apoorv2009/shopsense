"""Return eligibility (M4): the rules engine decides, the indexed section is cited.

Consistency (R4-5, LLD-6 L6g): the cited section's hash in the index must equal the hash of
the same section in the corpus. A mismatch means the index is stale, so the case escalates."""

from collections.abc import Mapping
from dataclasses import dataclass

from shopsense_api.application.ports.policy import PolicyIndex, PolicyStore
from shopsense_api.domain.policy.rules_engine import (
    Decision,
    Eligibility,
    NoApplicableRuleError,
    PolicyTieError,
    ReturnCase,
    decide,
)


@dataclass(frozen=True, slots=True)
class ReturnAssessment:
    eligibility: Eligibility
    reply: str
    rule_id: str | None
    citation: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class DecideReturn:
    store: PolicyStore
    index: PolicyIndex
    corpus_hashes: Mapping[str, str]

    async def run(self, case: ReturnCase) -> ReturnAssessment:
        try:
            decision = decide(case, await self.store.rules())
        except PolicyTieError as exc:
            return _escalate(f"policy tie between {exc.rule_ids}")
        except NoApplicableRuleError:
            return _escalate("no policy rule applies")
        chunk_id = f"{decision.rule.doc_id}#{decision.rule.section_id}"
        chunk = await self.index.get_chunk(chunk_id)
        if chunk is None or chunk.content_hash != self.corpus_hashes.get(chunk_id):
            return _escalate(f"policy index out of date for {chunk_id}")
        return ReturnAssessment(
            eligibility=decision.eligibility,
            reply=_reply(decision),
            rule_id=decision.rule.rule_id,
            citation=chunk_id,
            reason=(
                f"{decision.rule.rule_id} applies; "
                f"{decision.days_since_delivery} days since delivery"
            ),
        )


def _escalate(reason: str) -> ReturnAssessment:
    return ReturnAssessment(
        eligibility=Eligibility.ESCALATE,
        reply="A support specialist will review this request.",
        rule_id=None,
        citation=None,
        reason=reason,
    )


def _reply(decision: Decision) -> str:
    rule = decision.rule
    days = decision.days_since_delivery
    if decision.eligibility is Eligibility.ELIGIBLE:
        if rule.window_days is None:
            return "This item is eligible under our policy for this issue."
        return (
            f"Eligible. Items like this can be returned within {rule.window_days} days "
            f"of delivery, and {days} days have passed."
        )
    if decision.eligibility is Eligibility.NOT_ELIGIBLE:
        if rule.window_days is None:
            return "This product is not returnable under our policy."
        late = days - rule.window_days
        return f"Not eligible. The {rule.window_days}-day return window closed {late} days ago."
    if decision.eligibility is Eligibility.NEEDS_EVIDENCE:
        return "A photo is needed to check this claim. Please upload up to three clear photos."
    return "A support specialist will review this request."
