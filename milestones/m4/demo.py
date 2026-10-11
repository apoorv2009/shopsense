"""M4 demo: the rules engine decides return eligibility, RAG explains with citations, and the
three retrieval modes are compared on the same questions.

Prerequisites: policies ingested with `shopsense-ingest --rebuild`, and the M3 database.

  uv run python milestones/m4/demo.py
"""

import asyncio
from datetime import date

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from shopsense_api.adapters.policy.markdown_corpus import load_corpus
from shopsense_api.application.use_cases.decide_return import ReturnAssessment
from shopsense_api.application.use_cases.hybrid_search import Mode
from shopsense_api.domain.policy.rules_engine import ReturnCase
from shopsense_api.domain.values.untrusted_text import UntrustedText
from shopsense_api.entrypoints.composition import Container, container
from shopsense_api.entrypoints.logging_config import configure_logging
from shopsense_api.entrypoints.settings import REPO_ROOT, Settings

console = Console()
TODAY = date(2026, 10, 11)
POLICY_DIR = REPO_ROOT / "data" / "policies"
CASES: tuple[tuple[str, ReturnCase], ...] = (
    (
        "Power bank bought 10 days ago (electronics window says 15, accessory window says 7)",
        ReturnCase("electronics", True, "UPI", date(2026, 10, 1), TODAY, price_paise=179900),
    ),
    (
        "Laptop delivered 12 days ago",
        ReturnCase("electronics", False, "UPI", date(2026, 9, 29), TODAY, price_paise=5499000),
    ),
    (
        "Leaking cooking oil reported 90 minutes after delivery, no photo yet",
        ReturnCase(
            "groceries",
            False,
            "UPI",
            date(2026, 10, 10),
            TODAY,
            item_condition="damaged",
            reported_minutes=90,
            price_paise=42000,
        ),
    ),
    (
        "Damaged laptop: delivered yesterday, reported 10 hours later, photo verified",
        ReturnCase(
            "electronics",
            False,
            "UPI",
            date(2026, 10, 10),
            TODAY,
            item_condition="damaged",
            reported_minutes=600,
            photo_verified=True,
            price_paise=5499000,
        ),
    ),
)
QUESTIONS = (
    "Can I return an opened vitamin C serum?",
    "What is the refund timeline after I return an item?",
    "Do you deliver to Mars?",
)
MODES: tuple[Mode, ...] = ("dense", "hybrid", "hybrid_rerank")


async def show_decisions(app: Container) -> None:
    corpus = load_corpus(POLICY_DIR)
    deciding = app.decide_return(corpus)
    console.rule("[bold]1 · Return eligibility: rules engine decides, RAG cites[/bold]")
    for title, case in CASES:
        result: ReturnAssessment = await deciding.run(case)
        body = (
            f"{result.reply}\n[dim]rule {result.rule_id} · citation {result.citation} · "
            f"{result.eligibility}[/dim]"
        )
        console.print(Panel(body, title=title))


async def show_modes(app: Container) -> None:
    console.rule("[bold]2 · Retrieval: dense vs hybrid vs hybrid + rerank[/bold]")
    search = app.search_policy()
    table = Table("question", *MODES, show_lines=True)
    for question in ("return window for a power bank", "refund timeline after return"):
        tops = []
        for mode in MODES:
            hits = await search.run(question, limit=4, mode=mode)
            tops.append(hits[0].chunk.chunk_id if hits else "-")
        table.add_row(question, *tops)
    console.print(table)


async def show_answers(app: Container) -> None:
    console.rule("[bold]3 · Open questions: cited, number-checked, judged[/bold]")
    answerer = app.answer_policy()
    judge = app.judge()
    index = app.policy_index()
    for question in QUESTIONS:
        answer = await answerer.run(UntrustedText(question))
        if not answer.answered:
            console.print(Panel(answer.reply, title=question))
            continue
        texts = []
        for cid in answer.citations:
            chunk = await index.get_chunk(cid)
            if chunk:
                texts.append(chunk.text)
        verdict = await judge.run(UntrustedText(question), answer.reply, texts)
        cites = ", ".join(answer.citations)
        note = f"citations: {cites} · groundedness {verdict.score}/5"
        console.print(Panel(f"{answer.reply}\n[dim]{note}[/dim]", title=question))


async def main() -> None:
    configure_logging(json=False)
    async with container(Settings()) as app:
        await show_decisions(app)
        await show_modes(app)
        await show_answers(app)


if __name__ == "__main__":
    asyncio.run(main())
