"""M3 retrieval evaluation: does the right policy section come back for each question?

Metrics: hit@4 (an acceptable section is in the top 4) and MRR@10 (reciprocal rank of the
first acceptable section within the top 10). Dense retrieval only; M4 must beat this baseline."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from shopsense_api.application.use_cases.search_policy import SearchPolicy

TOP_K = 4
MRR_K = 10


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    case_id: str
    question: str
    category: str | None
    expected: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalOutcome:
    case_id: str
    question: str
    expected: tuple[str, ...]
    ranked: tuple[str, ...]
    rank: int | None

    @property
    def hit_at_4(self) -> bool:
        return self.rank is not None and self.rank <= TOP_K


@dataclass(frozen=True, slots=True)
class RetrievalReport:
    cases: int
    hit_at_4: float
    mrr_at_10: float


def load_cases(path: Path) -> list[RetrievalCase]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [
        RetrievalCase(r["id"], r["question"], r["category"], tuple(r["expected"])) for r in rows
    ]


async def run_retrieval(search: SearchPolicy, cases: list[RetrievalCase]) -> list[RetrievalOutcome]:
    outcomes = []
    for case in cases:
        hits = await search.run(case.question, limit=MRR_K, category=case.category)
        ranked = tuple(h.chunk.chunk_id for h in hits)
        rank = next((i + 1 for i, cid in enumerate(ranked) if cid in case.expected), None)
        outcomes.append(RetrievalOutcome(case.case_id, case.question, case.expected, ranked, rank))
    return outcomes


def summarise(outcomes: list[RetrievalOutcome]) -> RetrievalReport:
    total = len(outcomes)
    hits = sum(o.hit_at_4 for o in outcomes)
    reciprocal = sum(1 / o.rank for o in outcomes if o.rank is not None)
    return RetrievalReport(total, hits / total, reciprocal / total)


def save(outcomes: list[RetrievalOutcome], report: RetrievalReport, path: Path) -> None:
    payload = {
        "report": asdict(report),
        "cases": [
            {
                "id": o.case_id,
                "question": o.question,
                "expected": list(o.expected),
                "top_10": list(o.ranked),
                "rank": o.rank,
                "hit_at_4": o.hit_at_4,
            }
            for o in outcomes
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
