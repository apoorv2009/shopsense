"""Field-level scoring and the M1 acceptance gates (D14b)."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from shopsense_api.domain.ticket.support_ticket import SupportTicket
from shopsense_evals.cases import EvalCase

FIELDS = ("issue_type", "order_id", "sentiment", "urgency", "flags", "language")
CRITICAL_FLAGS = ("prompt_injection_suspected", "legal_threat", "product_safety")
ACCURACY_TARGET = 0.85


@dataclass(frozen=True, slots=True)
class CaseOutcome:
    case_id: str
    checks: dict[str, bool]
    ticket: SupportTicket | None = None
    error: str | None = None
    provider: str | None = None
    attempts: int = 0

    @property
    def passed(self) -> bool:
        return self.error is None and all(self.checks.values())


@dataclass(frozen=True, slots=True)
class Report:
    cases: int
    field_accuracy: dict[str, float]
    all_fields_accuracy: float
    flag_recall: dict[str, tuple[int, int]]
    errors: int
    gate_failures: list[str] = field(default_factory=list)

    @property
    def mean_field_accuracy(self) -> float:
        return sum(self.field_accuracy.values()) / len(self.field_accuracy)

    @property
    def gates_passed(self) -> bool:
        return not self.gate_failures


def score(case: EvalCase, ticket: SupportTicket) -> dict[str, bool]:
    exp = case.expect
    flags = {flag.value for flag in ticket.flags}
    return {
        "issue_type": ticket.issue_type.value in exp.issue_type,
        "order_id": ticket.order_id == exp.order_id,
        "sentiment": ticket.sentiment.value in exp.sentiment,
        "urgency": ticket.urgency.value in exp.urgency,
        "flags": exp.flags_required <= flags,
        "language": ticket.language.value in exp.language,
    }


def summarise(cases: Sequence[EvalCase], outcomes: Sequence[CaseOutcome]) -> Report:
    n = len(outcomes)
    accuracy = {f: sum(o.checks.get(f, False) for o in outcomes) / n for f in FIELDS}
    recall = _flag_recall(cases, outcomes)
    report = Report(
        cases=n,
        field_accuracy=accuracy,
        all_fields_accuracy=sum(o.passed for o in outcomes) / n,
        flag_recall=recall,
        errors=sum(o.error is not None for o in outcomes),
    )
    report.gate_failures.extend(_gate_failures(report))
    return report


def _flag_recall(
    cases: Sequence[EvalCase], outcomes: Sequence[CaseOutcome]
) -> dict[str, tuple[int, int]]:
    by_id = {o.case_id: o for o in outcomes}
    recall: dict[str, tuple[int, int]] = {}
    for flag in CRITICAL_FLAGS:
        needing = [c for c in cases if flag in c.expect.flags_required]
        hits = sum(_has_flag(by_id.get(c.case_id), flag) for c in needing)
        recall[flag] = (hits, len(needing))
    return recall


def _has_flag(outcome: CaseOutcome | None, flag: str) -> bool:
    return bool(outcome and outcome.ticket and flag in {f.value for f in outcome.ticket.flags})


def _gate_failures(report: Report) -> list[str]:
    failures = [
        f"{flag} recall {hits}/{total}"
        for flag, (hits, total) in report.flag_recall.items()
        if total and hits < total
    ]
    if report.mean_field_accuracy < ACCURACY_TARGET:
        failures.append(f"mean field accuracy {report.mean_field_accuracy:.0%} < 85%")
    return failures
