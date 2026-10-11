"""Writes realistic, noisy ticket text for each spec with an LLM (labels come from the spec)."""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import structlog
from pydantic import BaseModel, Field

from shopsense_api.application.ports.llm import LLMClient, StructuredRequest
from shopsense_evals.specs import TicketSpec

PROFILE = "ticket_generator"
BATCH_SIZE = 10
_ORDER_RE = re.compile(r"ORD-\d{6}", re.IGNORECASE)
log = structlog.get_logger(__name__)


class GeneratedTicket(BaseModel):
    spec_id: int
    text: str = Field(description="The customer's message, exactly as they would write it.")


class GeneratedBatch(BaseModel):
    tickets: list[GeneratedTicket]


@dataclass(frozen=True, slots=True)
class GeneratedCase:
    spec: TicketSpec
    text: str


async def generate(llm: LLMClient, specs: Sequence[TicketSpec]) -> list[GeneratedCase]:
    system = resources.files("shopsense_evals").joinpath("generator_prompt.md").read_text("utf-8")
    cases: list[GeneratedCase] = []
    for start in range(0, len(specs), BATCH_SIZE):
        batch = list(specs[start : start + BATCH_SIZE])
        request = StructuredRequest(PROFILE, system, _batch_message(batch), GeneratedBatch)
        response = await llm.generate_structured(request)
        cases.extend(_accept(batch, response.output))
    return cases


def _batch_message(batch: Sequence[TicketSpec]) -> str:
    rows = [
        {
            "spec_id": s.spec_id,
            "intent_example": s.seed_text,
            "issue_type": s.issue_type,
            "sentiment": s.sentiment,
            "order_id": s.order_id,
            "amount_rupees": s.amount_rupees,
            "must_include": s.flags,
            "language": s.language,
        }
        for s in batch
    ]
    return "Write one ticket per spec:\n" + json.dumps(rows, ensure_ascii=False, indent=1)


def _accept(batch: Sequence[TicketSpec], output: GeneratedBatch) -> list[GeneratedCase]:
    texts = {t.spec_id: t.text for t in output.tickets}
    accepted = []
    for spec in batch:
        text = texts.get(spec.spec_id, "")
        if _consistent(spec, text):
            accepted.append(GeneratedCase(spec, text))
        else:
            log.warning("generated_ticket_rejected", spec_id=spec.spec_id)
    return accepted


def _consistent(spec: TicketSpec, text: str) -> bool:
    found = {m.upper() for m in _ORDER_RE.findall(text)}
    expected = {spec.order_id} if spec.order_id else set()
    return bool(text.strip()) and found == expected


def write_suite(cases: Sequence[GeneratedCase], path: Path) -> None:
    lines = [
        json.dumps(
            {"id": f"T{c.spec.spec_id:03d}", "text": c.text, "expect": c.spec.expectation()},
            ensure_ascii=False,
        )
        for c in cases
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
