"""M4 tests: rules engine boundaries and precedence, grounding checks, fusion and consistency."""

from datetime import date
from pathlib import Path

import pytest
from qdrant_client import AsyncQdrantClient
from test_policy_m3 import (
    DIM,
    FakeReranker,
    HashingEmbedder,
    MemoryPolicyStore,
    ScriptedStructuredLLM,
    StaticPromptRepo,
    corpus,
)

from shopsense_api.adapters.policy.markdown_corpus import load_corpus
from shopsense_api.adapters.policy.qdrant_index import QdrantPolicyIndex
from shopsense_api.application.ports.policy import Hit
from shopsense_api.application.use_cases.answer_policy import (
    HANDOFF,
    AnswerPolicyQuestion,
    PolicyAnswerOut,
)
from shopsense_api.application.use_cases.decide_return import DecideReturn
from shopsense_api.application.use_cases.hybrid_search import (
    HybridSearch,
    reciprocal_rank_fusion,
)
from shopsense_api.application.use_cases.ingest_policies import IngestPolicies
from shopsense_api.domain.policy.chunks import PolicyChunk
from shopsense_api.domain.policy.grounding import encode_sparse, numbers_in, unsupported_numbers
from shopsense_api.domain.policy.model import (
    Evidence,
    Outcome,
    PolicyDocument,
    PolicyRule,
    RuleKind,
)
from shopsense_api.domain.policy.rules_engine import (
    Eligibility,
    PolicyTieError,
    ReturnCase,
    decide,
)
from shopsense_api.domain.values.untrusted_text import UntrustedText

CORPUS = Path(__file__).resolve().parents[4] / "data" / "policies"
D = date(2026, 10, 1)


@pytest.fixture(scope="module")
def rules() -> list[PolicyRule]:
    return [r for d in load_corpus(CORPUS) for s in d.sections for r in s.rules]


def case(days: int, **kw: object) -> ReturnCase:
    base: dict[str, object] = {
        "category": "electronics",
        "is_accessory": False,
        "payment_method": "UPI",
        "delivered_on": D,
        "today": date.fromordinal(D.toordinal() + days),
    }
    return ReturnCase(**(base | kw))  # type: ignore[arg-type]


# --- rules engine: windows ------------------------------------------------------------


@pytest.mark.parametrize(("days", "expected"), [(0, True), (15, True), (16, False)])
def test_electronics_window_boundaries(rules: list[PolicyRule], days: int, expected: bool) -> None:
    d = decide(case(days), rules)
    assert d.rule.rule_id == "ELE-RET-15"
    assert (d.eligibility is Eligibility.ELIGIBLE) is expected


@pytest.mark.parametrize(("days", "expected"), [(7, True), (8, False)])
def test_accessory_window_wins_over_electronics(
    rules: list[PolicyRule], days: int, expected: bool
) -> None:
    d = decide(case(days, is_accessory=True), rules)
    assert d.rule.rule_id == "ELE-ACC-7"
    assert (d.eligibility is Eligibility.ELIGIBLE) is expected


def test_apparel_uses_forty_five_days(rules: list[PolicyRule]) -> None:
    assert decide(case(45, category="apparel"), rules).rule.rule_id == "APP-RET-45"
    assert decide(case(46, category="apparel"), rules).eligibility is Eligibility.NOT_ELIGIBLE


def test_unknown_category_falls_back_to_general_thirty_days(rules: list[PolicyRule]) -> None:
    d = decide(case(30, category="furniture"), rules)
    assert d.rule.rule_id == "RET-GEN-30"
    assert d.eligibility is Eligibility.ELIGIBLE
    assert decide(case(31, category="furniture"), rules).eligibility is Eligibility.NOT_ELIGIBLE


# --- rules engine: conditions and precedence -------------------------------------------


def test_opened_beauty_is_not_returnable(rules: list[PolicyRule]) -> None:
    d = decide(case(1, category="beauty", item_condition="opened"), rules)
    assert d.rule.rule_id == "BEA-OPEN-NR"
    assert d.eligibility is Eligibility.NOT_ELIGIBLE


def test_unopened_beauty_has_seven_days(rules: list[PolicyRule]) -> None:
    d = decide(case(7, category="beauty", item_condition="unopened"), rules)
    assert d.rule.rule_id == "BEA-RET-7"
    assert d.eligibility is Eligibility.ELIGIBLE


def test_groceries_are_not_returnable_without_damage(rules: list[PolicyRule]) -> None:
    d = decide(case(1, category="groceries"), rules)
    assert d.rule.rule_id == "GRO-NR"
    assert d.eligibility is Eligibility.NOT_ELIGIBLE


def test_damaged_grocery_within_48_hours_needs_photo(rules: list[PolicyRule]) -> None:
    d = decide(case(0, category="groceries", reported_minutes=120), rules)
    assert d.rule.rule_id == "GRO-DMG-48H"
    assert d.rule.outcome is Outcome.REPLACEMENT_ONLY
    assert d.eligibility is Eligibility.NEEDS_EVIDENCE


def test_verified_photo_satisfies_evidence(rules: list[PolicyRule]) -> None:
    d = decide(case(0, category="groceries", reported_minutes=120, photo_verified=True), rules)
    assert d.eligibility is Eligibility.ELIGIBLE


@pytest.mark.parametrize(("minutes", "rule_id"), [(2880, "DMG-48H"), (2881, "ELE-RET-15")])
def test_forty_eight_hour_boundary(rules: list[PolicyRule], minutes: int, rule_id: str) -> None:
    d = decide(case(30, item_condition="damaged", reported_minutes=minutes), rules)
    assert d.rule.rule_id == rule_id


def test_damaged_electronics_within_48_hours_overrides_the_window(rules: list[PolicyRule]) -> None:
    d = decide(case(30, item_condition="damaged", reported_minutes=600, photo_verified=True), rules)
    assert d.rule.rule_id == "DMG-48H"
    assert d.eligibility is Eligibility.ELIGIBLE


def test_shipping_and_warranty_rules_never_decide_returns(rules: list[PolicyRule]) -> None:
    d = decide(case(3, item_condition="damaged", reported_minutes=60), rules)
    assert d.rule.kind in {RuleKind.RETURN_WINDOW, RuleKind.NOT_RETURNABLE, RuleKind.EXCEPTION}


def test_goodwill_and_cancellation_do_not_compete_with_returns(rules: list[PolicyRule]) -> None:
    kinds = {r.rule_id: r.kind for r in rules}
    assert kinds["GW-500"] is RuleKind.GOODWILL
    assert kinds["CAN-PRE-DISPATCH"] is RuleKind.CANCELLATION


def test_equal_specificity_with_different_outcomes_is_a_tie() -> None:
    def rule(rid: str, outcome: Outcome) -> PolicyRule:
        return PolicyRule(
            rule_id=rid,
            kind=RuleKind.RETURN_WINDOW,
            applies_to={"category": "toys"},
            window_days=5,
            outcome=outcome,
            overrides=(),
            evidence=Evidence.NONE,
            doc_id="d",
            section_id="1",
        )

    with pytest.raises(PolicyTieError, match=r"A-1|B-1"):
        decide(
            case(1, category="toys"),
            [rule("A-1", Outcome.RETURN), rule("B-1", Outcome.NOT_RETURNABLE)],
        )


def test_override_resolves_a_would_be_tie() -> None:
    base = {
        "kind": RuleKind.RETURN_WINDOW,
        "applies_to": {"category": "toys"},
        "window_days": 5,
        "evidence": Evidence.NONE,
        "doc_id": "d",
        "section_id": "1",
    }
    a = PolicyRule(rule_id="A-1", outcome=Outcome.RETURN, overrides=("B-1",), **base)  # type: ignore[arg-type]
    b = PolicyRule(rule_id="B-1", outcome=Outcome.NOT_RETURNABLE, overrides=(), **base)  # type: ignore[arg-type]
    assert decide(case(1, category="toys"), [a, b]).rule.rule_id == "A-1"


# --- grounding -------------------------------------------------------------------------


def test_numbers_are_normalised_for_separators() -> None:
    assert numbers_in("₹5,000 within 15 days") == {"5000", "15"}


def test_fabricated_window_is_unsupported() -> None:
    source = "Electronics can be returned within 15 days of delivery."
    assert unsupported_numbers("Return within 15 days.", [source]) == set()
    assert unsupported_numbers("Return within 20 days.", [source]) == {"20"}


def test_sparse_encoding_is_deterministic_and_ignores_stop_words() -> None:
    a = encode_sparse("the refund for my order")
    b = encode_sparse("refund order")
    assert a == b
    assert encode_sparse("the and of") == encode_sparse("")


def test_reciprocal_rank_fusion_prefers_agreement() -> None:
    def hit(cid: str) -> Hit:
        chunk = PolicyChunk(cid, "d", "1", "t", "x", (), ("*",), "h")
        return Hit(chunk, 0.0)

    fused = reciprocal_rank_fusion([[hit("a"), hit("b")], [hit("b"), hit("c")]])
    assert [h.chunk.chunk_id for h in fused] == ["b", "a", "c"]


# --- consistency and grounded answers --------------------------------------------------


async def _index(docs: list[PolicyDocument]) -> QdrantPolicyIndex:
    client = AsyncQdrantClient(location=":memory:")
    index = QdrantPolicyIndex(client, "m4", DIM)
    await IngestPolicies(MemoryPolicyStore(), index, HashingEmbedder()).run(docs)
    return index


async def test_stale_index_escalates() -> None:
    docs = corpus()
    index = await _index(docs)
    store = MemoryPolicyStore()
    store.docs = {d.doc_id: d for d in docs}
    hashes = {s.chunk_id: s.content_hash for d in docs for s in d.sections}
    hashes["returns-electronics#1"] = "not-the-current-hash"
    assessment = await DecideReturn(store, index, hashes).run(case(3))
    assert assessment.eligibility is Eligibility.ESCALATE
    assert "out of date" in assessment.reason


async def test_consistent_index_returns_the_decision_with_citation() -> None:
    docs = corpus()
    index = await _index(docs)
    store = MemoryPolicyStore()
    store.docs = {d.doc_id: d for d in docs}
    hashes = {s.chunk_id: s.content_hash for d in docs for s in d.sections}
    assessment = await DecideReturn(store, index, hashes).run(case(3))
    assert assessment.eligibility is Eligibility.ELIGIBLE
    assert assessment.citation == "returns-electronics#1"
    assert "15 days" in assessment.reply


async def test_answer_with_invented_number_is_blocked() -> None:
    docs = corpus()
    index = await _index(docs)
    search = HybridSearch(HashingEmbedder(), index, FakeReranker())
    hits = await search.run("electronics return window", limit=4)
    cited = next(h.chunk.chunk_id for h in hits if "15 days" in h.chunk.text)
    llm = ScriptedStructuredLLM(
        PolicyAnswerOut(
            can_answer=True, answer="Returns are allowed within 21 days.", citations=[cited]
        )
    )
    answer = await AnswerPolicyQuestion(llm, StaticPromptRepo(), search).run(
        UntrustedText("electronics return window"), mode="hybrid"
    )
    assert answer.reply == HANDOFF
    assert answer.blocked_numbers == ("21",)
