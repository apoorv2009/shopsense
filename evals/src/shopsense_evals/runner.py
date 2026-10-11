"""Runs triage over evaluation cases with bounded concurrency."""

import asyncio
from collections.abc import Sequence

from shopsense_api.application.use_cases.triage_ticket import TriageCommand, TriageTicket
from shopsense_api.domain.exceptions import DomainException
from shopsense_api.domain.values.untrusted_text import UntrustedText
from shopsense_evals.cases import EvalCase
from shopsense_evals.scoring import CaseOutcome, score


async def run_cases(
    triage: TriageTicket, cases: Sequence[EvalCase], concurrency: int = 4
) -> list[CaseOutcome]:
    limit = asyncio.Semaphore(concurrency)

    async def one(case: EvalCase) -> CaseOutcome:
        async with limit:
            return await _run_case(triage, case)

    return list(await asyncio.gather(*(one(c) for c in cases)))


async def _run_case(triage: TriageTicket, case: EvalCase) -> CaseOutcome:
    try:
        result = await triage.execute(TriageCommand(message=UntrustedText(case.text)))
    except DomainException as exc:
        return CaseOutcome(case.case_id, {}, error=f"{type(exc).__name__}: {exc}")
    return CaseOutcome(
        case_id=case.case_id,
        checks=score(case, result.ticket),
        ticket=result.ticket,
        provider=result.provider,
        attempts=result.attempts,
    )
