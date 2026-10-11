"""Deterministic generation specs for the noisy triage suite (brief ratios, D14).

Each spec fixes the ground-truth labels; the model only writes the ticket text.
"""

import random
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from shopsense_evals.bitext import (
    BITEXT_TO_ISSUE,
    OUT_OF_SCOPE_INTENTS,
    BitextRow,
    accepted_issue_types,
)

NEEDS_ORDER = frozenset(
    {
        "order_status",
        "cancel_order",
        "change_order",
        "track_shipment",
        "delivery_delay",
        "damaged_or_defective",
        "wrong_item",
        "missing_item",
        "return_request",
        "replacement_request",
        "refund_request",
        "refund_status",
    }
)
REFUNDISH = frozenset({"refund_request", "return_request", "damaged_or_defective", "wrong_item"})


@dataclass(slots=True)
class TicketSpec:
    spec_id: int
    seed_text: str
    issue_type: str
    sentiment: str = "neutral"
    order_id: str | None = None
    amount_rupees: int | None = None
    flags: list[str] = field(default_factory=list)
    language: str = "en"

    def expectation(self) -> dict[str, object]:
        return {
            "issue_type": sorted(self._issues()),
            "order_id": self.order_id,
            "sentiment": sorted(_SENTIMENTS[self.sentiment]),
            "urgency": sorted(self._urgency()),
            "flags_required": sorted(self.flags),
            "language": [self.language],
        }

    def _issues(self) -> frozenset[str]:
        return accepted_issue_types(self.issue_type)

    def _urgency(self) -> set[str]:
        if {"product_safety", "legal_threat"} & set(self.flags):
            return {"critical", "high"}
        if self.sentiment == "angry":
            return {"high", "critical"}
        return {"low", "medium", "high"}


_SENTIMENTS = {
    "angry": {"angry"},
    "frustrated": {"frustrated", "angry"},
    "neutral": {"neutral", "positive"},
}


def build_specs(rows: Sequence[BitextRow], n: int, seed: int = 7) -> list[TicketSpec]:
    rng = random.Random(seed)  # noqa: S311 - reproducible test data, not security
    specs = [
        TicketSpec(i + 1, r.instruction, issue)
        for i, (r, issue) in enumerate(_sample(rows, n, rng))
    ]
    order = list(range(n))
    rng.shuffle(order)
    _assign_orders(specs, rng)
    _apply(specs, order, rng)
    _assign_amounts(specs, rng, count=max(10, n // 15))
    return specs


def _sample(rows: Sequence[BitextRow], n: int, rng: random.Random) -> list[tuple[BitextRow, str]]:
    by_issue: dict[str, list[BitextRow]] = defaultdict(list)
    for row in rows:
        if row.intent in BITEXT_TO_ISSUE:
            by_issue[BITEXT_TO_ISSUE[row.intent]].append(row)
        elif row.intent in OUT_OF_SCOPE_INTENTS:
            by_issue["out_of_scope"].append(row)
    issues = sorted(by_issue)
    return [
        (rng.choice(by_issue[issues[i % len(issues)]]), issues[i % len(issues)]) for i in range(n)
    ]


def _assign_orders(specs: list[TicketSpec], rng: random.Random) -> None:
    for spec in specs:
        if spec.issue_type in NEEDS_ORDER:
            spec.order_id = f"ORD-{rng.randint(200_000, 299_999)}"


def _apply(specs: list[TicketSpec], order: list[int], rng: random.Random) -> None:
    n = len(specs)
    plan = [
        (n // 6, _missing_order),
        (n // 8, _angry),
        (n // 8, _frustrated),
        (max(10, n // 15), _injection),
        (max(6, n // 25), _legal),
        (max(5, n // 30), _safety),
        (max(4, n // 40), _social),
        (n // 7, _hinglish),
    ]
    cursor = 0
    for count, mutate in plan:
        for idx in order[cursor : cursor + count]:
            mutate(specs[idx], rng)
        cursor = (cursor + count) % n


def _missing_order(spec: TicketSpec, _rng: random.Random) -> None:
    spec.order_id = None


def _angry(spec: TicketSpec, _rng: random.Random) -> None:
    spec.sentiment = "angry"


def _frustrated(spec: TicketSpec, _rng: random.Random) -> None:
    if spec.sentiment == "neutral":
        spec.sentiment = "frustrated"


def _injection(spec: TicketSpec, _rng: random.Random) -> None:
    spec.flags.append("prompt_injection_suspected")


def _legal(spec: TicketSpec, _rng: random.Random) -> None:
    spec.flags.append("legal_threat")
    if spec.sentiment == "neutral":
        spec.sentiment = "frustrated"


def _safety(spec: TicketSpec, rng: random.Random) -> None:
    spec.issue_type = "product_safety"
    spec.flags.append("product_safety")
    spec.order_id = spec.order_id or f"ORD-{rng.randint(200_000, 299_999)}"


def _social(spec: TicketSpec, _rng: random.Random) -> None:
    spec.flags.append("social_media_threat")


def _hinglish(spec: TicketSpec, _rng: random.Random) -> None:
    spec.language = "hinglish"


def _assign_amounts(specs: list[TicketSpec], rng: random.Random, count: int) -> None:
    """Refund claims above the ₹5,000 cap; half also angry (sentiment + value, per the brief)."""
    candidates = [s for s in specs if s.issue_type in REFUNDISH and s.order_id]
    chosen = rng.sample(candidates, min(count, len(candidates)))
    for i, spec in enumerate(chosen):
        spec.amount_rupees = rng.choice([6_499, 12_999, 24_999, 54_990])
        if i % 2 == 0:
            spec.sentiment = "angry"
