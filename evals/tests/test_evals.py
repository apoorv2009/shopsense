from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from shopsense_api.application.ports.llm import StructuredRequest, StructuredResponse, TokenUsage
from shopsense_api.domain.ticket.support_ticket import SupportTicket
from shopsense_evals.bitext import BitextRow, accepted_issue_types
from shopsense_evals.cases import EvalCase, expectation_from_dict, load_cases
from shopsense_evals.generator import GeneratedBatch, GeneratedTicket, generate
from shopsense_evals.scoring import CaseOutcome, score, summarise
from shopsense_evals.specs import build_specs

GOLDEN = Path(__file__).resolve().parents[1] / "data" / "golden.jsonl"


def ticket(**overrides: Any) -> SupportTicket:
    fields: dict[str, Any] = {
        "issue_type": "refund_request",
        "secondary_issues": [],
        "order_id": "ORD-100003",
        "product_category_hint": None,
        "claimed_amount_paise": None,
        "sentiment": "angry",
        "urgency": "high",
        "flags": ["legal_threat"],
        "language": "en",
        "summary": "s",
    }
    return SupportTicket.model_validate(fields | overrides)


def case(case_id: str = "C1", **expect: Any) -> EvalCase:
    raw: dict[str, Any] = {
        "issue_type": ["refund_request"],
        "order_id": "ORD-100003",
        "sentiment": ["angry"],
        "urgency": ["high", "critical"],
        "flags_required": ["legal_threat"],
        "language": ["en"],
    }
    return EvalCase(case_id, "text", expectation_from_dict(raw | expect), "test")


def test_golden_set_has_20_cases_with_brief_coverage() -> None:
    cases = load_cases(GOLDEN, "golden")
    assert len(cases) == 20
    flags = Counter(f for c in cases for f in c.expect.flags_required)
    assert flags["prompt_injection_suspected"] >= 2
    assert flags["legal_threat"] >= 2
    assert flags["product_safety"] >= 1
    assert sum("angry" in c.expect.sentiment for c in cases) >= 3
    assert sum(c.expect.order_id is None for c in cases) >= 2


def test_score_all_fields() -> None:
    assert all(score(case(), ticket()).values())


def test_score_detects_wrong_fields() -> None:
    checks = score(case(), ticket(order_id=None, flags=[], sentiment="neutral"))
    assert not checks["order_id"]
    assert not checks["flags"]
    assert not checks["sentiment"]
    assert checks["issue_type"]


def test_gates_fail_on_missed_critical_flag() -> None:
    cases = [case("C1"), case("C2")]
    outcomes = [
        CaseOutcome("C1", score(cases[0], ticket()), ticket=ticket()),
        CaseOutcome("C2", score(cases[1], ticket(flags=[])), ticket=ticket(flags=[])),
    ]
    report = summarise(cases, outcomes)
    assert report.flag_recall["legal_threat"] == (1, 2)
    assert not report.gates_passed


def test_gates_pass_when_everything_correct() -> None:
    cases = [case("C1")]
    report = summarise(cases, [CaseOutcome("C1", score(cases[0], ticket()), ticket=ticket())])
    assert report.gates_passed
    assert report.mean_field_accuracy == 1.0


def test_errors_count_as_failures() -> None:
    report = summarise([case("C1")], [CaseOutcome("C1", {}, error="TriageFailed")])
    assert report.errors == 1
    assert not report.gates_passed


def test_equivalent_issue_types() -> None:
    assert "track_shipment" in accepted_issue_types("order_status")
    assert accepted_issue_types("policy_question") == {"policy_question"}


ROWS = [
    BitextRow(f"example {intent} {i}", intent)
    for intent in [
        "track_order",
        "request_refund",
        "return_product",
        "human_agent",
        "return_policy",
        "damaged_delivery",
        "change_account",
    ]
    for i in range(5)
]


def test_specs_follow_brief_ratios() -> None:
    specs = build_specs(ROWS, n=150, seed=1)
    assert len(specs) == 150
    flags = Counter(f for s in specs for f in s.flags)
    assert flags["prompt_injection_suspected"] >= 10
    assert flags["legal_threat"] >= 2
    assert flags["product_safety"] >= 1
    assert sum(s.sentiment == "angry" for s in specs) >= 150 // 8
    assert sum(s.language == "hinglish" for s in specs) >= 20
    assert {s.issue_type for s in specs} >= {"request_human", "out_of_scope", "policy_question"}
    above_cap = [s for s in specs if s.amount_rupees and s.amount_rupees > 5_000]
    assert len(above_cap) >= 10
    assert any(s.sentiment == "angry" for s in above_cap)


def test_specs_are_deterministic() -> None:
    a, b = build_specs(ROWS, 40, seed=3), build_specs(ROWS, 40, seed=3)
    assert [s.expectation() for s in a] == [s.expectation() for s in b]


class EchoGenerator:
    """Fake LLM: writes a ticket per spec, deliberately breaking the order id of spec 2."""

    async def generate_structured[T: BaseModel](
        self, request: StructuredRequest[T]
    ) -> StructuredResponse[T]:
        import json

        specs = json.loads(request.user_message.split("\n", 1)[1])
        tickets = [
            GeneratedTicket(
                spec_id=s["spec_id"],
                text=f"help with {s['order_id'] if s['spec_id'] != 2 else 'ORD-999999'}"
                if s["order_id"]
                else "help please",
            )
            for s in specs
        ]
        output = GeneratedBatch(tickets=tickets)
        assert isinstance(output, request.output_type)
        return StructuredResponse(output, "fake", "fake", TokenUsage(1, 1))


async def test_generator_rejects_inconsistent_tickets() -> None:
    specs = build_specs(ROWS, n=12, seed=5)
    cases = await generate(EchoGenerator(), specs)
    ids = {c.spec.spec_id for c in cases}
    spec2 = next(s for s in specs if s.spec_id == 2)
    assert (2 not in ids) == bool(spec2.order_id)
    assert len(cases) >= len(specs) - 1


def test_content_filter_block_counts_as_caught_injection() -> None:
    cases = [case("C1", flags_required=["prompt_injection_suspected"])]
    report = summarise(cases, [CaseOutcome("C1", {}, error="LLMRefused", blocked=True)])
    assert report.flag_recall["prompt_injection_suspected"] == (1, 1)
    assert report.blocked == 1
    assert report.errors == 0
