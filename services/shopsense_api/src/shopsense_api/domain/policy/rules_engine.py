"""Return-eligibility rules engine (LLD-6 L6c, L6d). Deterministic and pure: the LLM never
decides a window, amount or eligibility (M4 decision R4-1).

Precedence: explicit overrides remove a rule; the candidate with the most conditions wins;
two survivors with equal specificity and different outcomes is a policy error (PolicyTieError)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from shopsense_api.domain.policy.model import Evidence, Outcome, PolicyRule, RuleKind

DECISION_KINDS = frozenset({RuleKind.RETURN_WINDOW, RuleKind.NOT_RETURNABLE, RuleKind.EXCEPTION})


class Eligibility(StrEnum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    NEEDS_EVIDENCE = "needs_evidence"
    ESCALATE = "escalate"


class PolicyTieError(Exception):
    """Two equally specific rules disagree; loading or deciding fails closed."""

    def __init__(self, rule_ids: list[str]) -> None:
        super().__init__(f"unresolved precedence tie: {rule_ids}")
        self.rule_ids = rule_ids


class NoApplicableRuleError(Exception):
    """No decision rule applies to the case (the corpus should always contain a general rule)."""


@dataclass(frozen=True, slots=True)
class ReturnCase:
    category: str
    is_accessory: bool
    payment_method: str
    delivered_on: date
    today: date
    item_condition: str | None = None
    reported_minutes: int | None = None
    photo_verified: bool = False
    price_paise: int = 0

    @property
    def days_since_delivery(self) -> int:
        return (self.today - self.delivered_on).days


@dataclass(frozen=True, slots=True)
class Decision:
    rule: PolicyRule
    eligibility: Eligibility
    days_since_delivery: int


def decide(case: ReturnCase, rules: Sequence[PolicyRule]) -> Decision:
    candidates = [r for r in rules if r.kind in DECISION_KINDS and _matches(r, case)]
    if not candidates:
        raise NoApplicableRuleError(f"no rule for {case.category}")
    overridden = {o for r in candidates for o in r.overrides}
    live = [r for r in candidates if r.rule_id not in overridden]
    if not live:
        raise PolicyTieError(sorted(r.rule_id for r in candidates))
    top = max(len(r.applies_to) for r in live)
    best = [r for r in live if len(r.applies_to) == top]
    if len({(r.outcome, r.window_days) for r in best}) > 1:
        raise PolicyTieError(sorted(r.rule_id for r in best))
    rule = sorted(best, key=lambda r: r.rule_id)[0]
    return Decision(rule, _eligibility(rule, case), case.days_since_delivery)


def _matches(rule: PolicyRule, case: ReturnCase) -> bool:
    return all(_condition_holds(key, value, case) for key, value in rule.applies_to.items())


def _condition_holds(key: str, value: object, case: ReturnCase) -> bool:
    if key == "category":
        return case.category == value
    if key == "is_accessory":
        return case.is_accessory is value
    if key == "item_condition":
        return case.item_condition == value
    if key == "payment_method":
        return case.payment_method == value
    if key == "reported_within_hours":
        return case.reported_minutes is not None and case.reported_minutes <= int(str(value)) * 60
    if key == "price_below_paise":
        return case.price_paise < int(str(value))
    return False


def _eligibility(rule: PolicyRule, case: ReturnCase) -> Eligibility:
    if rule.outcome is Outcome.NOT_RETURNABLE:
        return Eligibility.NOT_ELIGIBLE
    if rule.outcome is Outcome.ESCALATE:
        return Eligibility.ESCALATE
    if rule.evidence is Evidence.PHOTO and not case.photo_verified:
        return Eligibility.NEEDS_EVIDENCE
    if rule.window_days is not None and case.days_since_delivery > rule.window_days:
        return Eligibility.NOT_ELIGIBLE
    return Eligibility.ELIGIBLE
