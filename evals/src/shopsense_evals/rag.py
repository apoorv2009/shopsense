"""M4 evaluation: rules-engine decisions, retrieval modes, and grounded open answers.

- Decisions: facts in, rule and eligibility out. Deterministic, so expected accuracy is 100%.
- Retrieval: dense, hybrid and hybrid + rerank on the same questions (see retrieval.py).
- Open questions: every answer's numbers are re-checked independently of the use case, and
  an LLM judge grades groundedness on the answers that were delivered."""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from shopsense_api.application.ports.policy import PolicyStore
from shopsense_api.application.use_cases.judge_groundedness import GroundednessJudge
from shopsense_api.domain.policy.grounding import unsupported_numbers
from shopsense_api.domain.policy.rules_engine import (
    NoApplicableRuleError,
    PolicyTieError,
    ReturnCase,
    decide,
)
from shopsense_api.domain.values.untrusted_text import UntrustedText
from shopsense_api.entrypoints.composition import Container


@dataclass(frozen=True, slots=True)
class DecisionCase:
    case_id: str
    note: str
    case: ReturnCase
    expect_rule: str
    expect_eligibility: str


def load_decisions(path: Path) -> list[DecisionCase]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        case = ReturnCase(
            category=row["category"],
            is_accessory=row["is_accessory"],
            payment_method=row["payment_method"],
            delivered_on=date.fromisoformat(row["delivered_on"]),
            today=date.fromisoformat(row["today"]),
            item_condition=row["item_condition"],
            reported_minutes=row["reported_minutes"],
            photo_verified=row["photo_verified"],
            price_paise=row["price_paise"],
        )
        out.append(
            DecisionCase(
                row["id"],
                row["note"],
                case,
                row["expect"]["rule_id"],
                row["expect"]["eligibility"],
            )
        )
    return out


async def run_decisions(store: PolicyStore, cases: list[DecisionCase]) -> list[dict[str, Any]]:
    rules = await store.rules()
    results = []
    for c in cases:
        try:
            decision = decide(c.case, rules)
            rule_id, eligibility = decision.rule.rule_id, decision.eligibility.value
        except (PolicyTieError, NoApplicableRuleError) as exc:
            rule_id, eligibility = type(exc).__name__, "error"
        correct = rule_id == c.expect_rule and eligibility == c.expect_eligibility
        results.append(
            {
                "id": c.case_id,
                "note": c.note,
                "expected": [c.expect_rule, c.expect_eligibility],
                "got": [rule_id, eligibility],
                "correct": correct,
            }
        )
    return results


async def run_open(
    app: Container, judge: GroundednessJudge, questions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    answerer = app.answer_policy()
    index = app.policy_index()
    results = []
    for q in questions:
        answer = await answerer.run(UntrustedText(q["question"]), category=q["category"])
        texts = []
        for cid in answer.citations:
            chunk = await index.get_chunk(cid)
            texts.append(chunk.text if chunk else "")
        fabricated = sorted(unsupported_numbers(answer.reply, texts)) if answer.answered else []
        verdict = None
        if answer.answered:
            v = await judge.run(UntrustedText(q["question"]), answer.reply, texts)
            verdict = {"score": v.score, "supported": v.supported}
        results.append(
            {
                "id": q["id"],
                "question": q["question"],
                "answered": answer.answered,
                "reply": answer.reply,
                "citations": list(answer.citations),
                "blocked_numbers": list(answer.blocked_numbers),
                "fabricated_in_delivered_reply": fabricated,
                "judge": verdict,
            }
        )
    return results


def summarise_open(results: list[dict[str, Any]]) -> dict[str, Any]:
    answered = [r for r in results if r["answered"]]
    scores = [r["judge"]["score"] for r in answered]
    return {
        "questions": len(results),
        "answered": len(answered),
        "handed_off": len(results) - len(answered),
        "fabrication_attempts_blocked": sum(len(r["blocked_numbers"]) > 0 for r in results),
        "fabricated_in_delivered_replies": sum(
            len(r["fabricated_in_delivered_reply"]) for r in results
        ),
        "groundedness_mean": round(sum(scores) / len(scores), 2) if scores else None,
        "groundedness_supported_share": (
            round(sum(r["judge"]["supported"] for r in answered) / len(answered), 2)
            if answered
            else None
        ),
    }
