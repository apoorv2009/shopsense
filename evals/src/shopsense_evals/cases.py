"""Evaluation cases and their expected triage fields."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Expectation:
    issue_type: frozenset[str]
    order_id: str | None
    sentiment: frozenset[str]
    urgency: frozenset[str]
    flags_required: frozenset[str]
    language: frozenset[str]


@dataclass(frozen=True, slots=True)
class EvalCase:
    case_id: str
    text: str
    expect: Expectation
    source: str


def expectation_from_dict(raw: dict[str, Any]) -> Expectation:
    return Expectation(
        issue_type=frozenset(raw["issue_type"]),
        order_id=raw["order_id"],
        sentiment=frozenset(raw["sentiment"]),
        urgency=frozenset(raw["urgency"]),
        flags_required=frozenset(raw["flags_required"]),
        language=frozenset(raw.get("language", ["en", "hinglish", "other"])),
    )


def load_cases(path: Path, source: str) -> list[EvalCase]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        cases.append(EvalCase(raw["id"], raw["text"], expectation_from_dict(raw["expect"]), source))
    return cases
