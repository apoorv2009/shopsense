"""Evaluation CLI.

shopsense-eval generate-suite --n 150           # one-time: write evals/data/triage_suite.jsonl
shopsense-eval triage --suite all --runs 3      # field accuracy + zero-tolerance gates
"""

import argparse
import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.table import Table

from shopsense_api.adapters.llm.gateway import AgentProfile, LLMGateway
from shopsense_api.adapters.llm.provider import ModelRoute
from shopsense_api.application.use_cases.triage_ticket import TriageTicket
from shopsense_api.entrypoints.composition import PRIMARY, container
from shopsense_api.entrypoints.logging_config import configure_logging
from shopsense_api.entrypoints.settings import REPO_ROOT, Settings
from shopsense_evals.bitext import load_rows
from shopsense_evals.cases import EvalCase, load_cases
from shopsense_evals.generator import generate, write_suite
from shopsense_evals.runner import run_cases
from shopsense_evals.scoring import FIELDS, CaseOutcome, Report, summarise
from shopsense_evals.specs import build_specs

DATA = REPO_ROOT / "evals" / "data"
RESULTS = REPO_ROOT / "evals" / "results"
BITEXT = REPO_ROOT / "data" / "raw" / "bitext" / "bitext-retail-ecommerce.csv"
console = Console()


def load_suite(name: str) -> list[EvalCase]:
    golden = load_cases(DATA / "golden.jsonl", "golden")
    if name == "golden":
        return golden
    generated = load_cases(DATA / "triage_suite.jsonl", "generated")
    return generated if name == "generated" else golden + generated


async def cmd_triage(args: argparse.Namespace) -> int:
    async with container(Settings()) as app:
        return await _triage_runs(app.triage(args.provider), args)


async def _triage_runs(triage: TriageTicket, args: argparse.Namespace) -> int:
    cases = load_suite(args.suite)
    reports = []
    for run in range(1, args.runs + 1):
        outcomes = await run_cases(triage, cases, concurrency=args.concurrency)
        report = summarise(cases, outcomes)
        reports.append(report)
        print_report(f"Run {run}/{args.runs} · {args.suite} · {args.provider}", report)
        save(outcomes, report, RESULTS / f"m1_triage_{args.suite}_{args.provider}_run{run}.json")
    return 0 if all(r.gates_passed for r in reports) else 1


async def cmd_generate(args: argparse.Namespace) -> int:
    settings = Settings()
    route = ModelRoute(PRIMARY, settings.primary_deployment, 8_000, 180.0)
    specs = build_specs(load_rows(BITEXT), n=args.n, seed=args.seed)
    async with container(settings) as app:
        llm = LLMGateway({"ticket_generator": AgentProfile((route,))}, app.providers)
        cases = await generate(llm, specs)
    write_suite(cases, DATA / "triage_suite.jsonl")
    console.print(f"Wrote {len(cases)}/{len(specs)} tickets to {DATA / 'triage_suite.jsonl'}")
    return 0


def print_report(title: str, report: Report) -> None:
    table = Table(title=title)
    for column in ("Field", "Accuracy"):
        table.add_column(column)
    for name in FIELDS:
        table.add_row(name, f"{report.field_accuracy[name]:.0%}")
    table.add_row("[b]mean[/b]", f"[b]{report.mean_field_accuracy:.0%}[/b]")
    table.add_row("all fields correct", f"{report.all_fields_accuracy:.0%}")
    console.print(table)
    for flag, (hits, total) in report.flag_recall.items():
        console.print(f"  {flag} recall: {hits}/{total}")
    status = (
        "[green]PASS[/green]" if report.gates_passed else f"[red]FAIL[/red] {report.gate_failures}"
    )
    console.print(f"  errors: {report.errors} · gates: {status}\n")


def save(outcomes: Sequence[CaseOutcome], report: Report, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "field_accuracy": report.field_accuracy,
        "all_fields_accuracy": report.all_fields_accuracy,
        "flag_recall": report.flag_recall,
        "gate_failures": report.gate_failures,
        "cases": [
            {
                "id": o.case_id,
                "checks": o.checks,
                "error": o.error,
                "provider": o.provider,
                "ticket": o.ticket.model_dump(mode="json") if o.ticket else None,
            }
            for o in outcomes
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(prog="shopsense-eval")
    sub = parser.add_subparsers(dest="command", required=True)
    triage = sub.add_parser("triage")
    triage.add_argument("--suite", choices=["golden", "generated", "all"], default="golden")
    triage.add_argument("--provider", default=PRIMARY)
    triage.add_argument("--runs", type=int, default=1)
    triage.add_argument("--concurrency", type=int, default=4)
    gen = sub.add_parser("generate-suite")
    gen.add_argument("--n", type=int, default=150)
    gen.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    configure_logging(json=Settings().log_json)
    handler = cmd_triage if args.command == "triage" else cmd_generate
    raise SystemExit(asyncio.run(handler(args)))
