"""Evaluation CLI.

shopsense-eval generate-suite --n 150           # one-time: write evals/data/triage_suite.jsonl
shopsense-eval triage --suite all --runs 3      # field accuracy + zero-tolerance gates
"""

import argparse
import asyncio
import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.table import Table

from order_platform.entrypoints.composition import Database
from order_platform.entrypoints.seed import seed
from order_platform.entrypoints.settings import Settings as OrderPlatformSettings
from shopsense_api.adapters.llm.gateway import AgentProfile, LLMGateway
from shopsense_api.adapters.llm.provider import ModelRoute
from shopsense_api.application.use_cases.triage_ticket import TriageTicket
from shopsense_api.entrypoints.composition import PRIMARY, container
from shopsense_api.entrypoints.logging_config import configure_logging
from shopsense_api.entrypoints.settings import REPO_ROOT, Settings
from shopsense_evals import rag, retrieval
from shopsense_evals.bitext import load_rows
from shopsense_evals.cases import EvalCase, load_cases
from shopsense_evals.generator import generate, write_suite
from shopsense_evals.runner import run_cases
from shopsense_evals.scoring import FIELDS, CaseOutcome, Report, summarise
from shopsense_evals.specs import build_specs
from shopsense_evals.tool_use import (
    ToolOutcome,
    ToolReport,
    load_tool_cases,
    run_tool_cases,
    summarise_tool_use,
)

DATA = REPO_ROOT / "evals" / "data"
RESULTS = REPO_ROOT / "evals" / "results"
BITEXT = REPO_ROOT / "data" / "raw" / "bitext" / "bitext-retail-ecommerce.csv"
console = Console()
TOOL_ANCHOR = date(2026, 10, 11)


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


async def cmd_tool_use(args: argparse.Namespace) -> int:
    cases = load_tool_cases(DATA / "tool_use.jsonl")
    reports = []
    async with container(Settings()) as app:
        agent = app.order_actions(args.provider)
        for run in range(1, args.runs + 1):
            await _reseed()
            outcomes = await run_tool_cases(agent, cases, run_tag=f"eval{run}")
            report = summarise_tool_use(outcomes)
            reports.append(report)
            title = f"Run {run}/{args.runs} · tool use · {args.provider}"
            print_tool_report(title, outcomes, report)
            save_tool(outcomes, report, RESULTS / f"m2_tool_use_{args.provider}_run{run}.json")
    return 0 if all(r.gates_passed for r in reports) else 1


async def cmd_retrieval(args: argparse.Namespace) -> int:
    cases = retrieval.load_cases(DATA / "retrieval.jsonl")
    async with container(Settings()) as app:
        search = app.search_policy()
        traps = retrieval.trap_ids(cases)
        for mode in args.modes:
            for run in range(1, args.runs + 1):
                outcomes = await retrieval.run_retrieval(search, cases, mode)
                report = retrieval.summarise(outcomes, traps)
                console.print(
                    f"Run {run}/{args.runs} · retrieval ({mode}) · {report.cases} questions"
                )
                p1 = report.precision_at_1_traps
                console.print(
                    f"hit@4 {report.hit_at_4:.0%} · MRR@10 {report.mrr_at_10:.3f} · "
                    f"trap p@1 {p1:.0%}"
                    if p1 is not None
                    else f"hit@4 {report.hit_at_4:.0%}"
                )
                name = f"m4_retrieval_{mode}_run{run}.json"
                retrieval.save(outcomes, report, RESULTS / name)
    return 0


async def cmd_rag(args: argparse.Namespace) -> int:
    decisions = rag.load_decisions(DATA / "decisions.jsonl")
    questions = [
        json.loads(x)
        for x in (DATA / "open_policy.jsonl").read_text(encoding="utf-8").splitlines()
        if x
    ]
    cases = retrieval.load_cases(DATA / "retrieval.jsonl")
    traps = retrieval.trap_ids(cases)
    async with container(Settings()) as app:
        decided = await rag.run_decisions(app.policy_store(), decisions)
        correct = sum(r["correct"] for r in decided)
        console.print(f"Decisions: {correct}/{len(decided)} correct")
        retrieval_rows = {}
        for mode in args.modes:
            outcomes = await retrieval.run_retrieval(app.search_policy(), cases, mode)
            report = retrieval.summarise(outcomes, traps)
            retrieval_rows[mode] = asdict(report)
            retrieval.save(outcomes, report, RESULTS / f"m4_retrieval_{mode}.json")
            p1 = report.precision_at_1_traps or 0.0
            console.print(
                f"Retrieval {mode}: hit@4 {report.hit_at_4:.0%} · "
                f"MRR@10 {report.mrr_at_10:.3f} · trap p@1 {p1:.0%}"
            )
        judge = app.judge()
        open_rows = await rag.run_open(app, judge, questions)
        summary = rag.summarise_open(open_rows)
        console.print(f"Open questions: {summary}")
    payload = {
        "decisions": decided,
        "retrieval": retrieval_rows,
        "open": open_rows,
        "summary": summary,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "m4_rag.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    gates = correct == len(decided) and summary["fabricated_in_delivered_replies"] == 0
    return 0 if gates else 1


async def _reseed() -> None:
    database = Database(OrderPlatformSettings())
    try:
        await seed(database.engine, TOOL_ANCHOR, reset=True)
    finally:
        await database.aclose()


def print_tool_report(title: str, outcomes: Sequence[ToolOutcome], report: ToolReport) -> None:
    table = Table("Case", "Group", "Tools called", "Outcome", "Checks", title=title)
    for o in outcomes:
        failed = [k for k, ok in {**o.checks, **o.safety}.items() if not ok]
        mark = "[green]PASS[/green]" if o.passed else f"[red]{','.join(failed)}[/red]"
        table.add_row(o.case_id, o.group, " > ".join(o.tools), o.outcome, mark)
    console.print(table)
    acc = " · ".join(f"{k} {v:.0%}" for k, v in report.check_accuracy.items())
    console.print(f"  accuracy (all checks) {report.accuracy:.0%} · {acc}")
    status = "[green]PASS[/green]" if report.gates_passed else "[red]FAIL[/red]"
    violations = report.safety_violations or "none"
    console.print(f"  safety violations: {violations} · gates: {status}\n")


def save_tool(outcomes: Sequence[ToolOutcome], report: ToolReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "accuracy": report.accuracy,
        "check_accuracy": report.check_accuracy,
        "safety_violations": report.safety_violations,
        "cases": [
            {
                "id": o.case_id,
                "group": o.group,
                "checks": o.checks,
                "safety": o.safety,
                "tools": o.tools,
                "writes": o.writes,
                "outcome": o.outcome,
                "reply": o.reply,
            }
            for o in outcomes
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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
    console.print(f"  blocked by content filter: {report.blocked} · errors: {report.errors}")
    console.print(f"  gates: {status}\n")


def save(outcomes: Sequence[CaseOutcome], report: Report, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "field_accuracy": report.field_accuracy,
        "all_fields_accuracy": report.all_fields_accuracy,
        "flag_recall": report.flag_recall,
        "gate_failures": report.gate_failures,
        "blocked": report.blocked,
        "errors": report.errors,
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
    triage.add_argument("--concurrency", type=int, default=2)
    tool = sub.add_parser("tool-use")
    tool.add_argument("--provider", default=PRIMARY)
    tool.add_argument("--runs", type=int, default=1)
    rag_cmd = sub.add_parser("rag")
    rag_cmd.add_argument(
        "--modes",
        nargs="+",
        choices=["dense", "hybrid", "hybrid_rerank"],
        default=["dense", "hybrid", "hybrid_rerank"],
    )
    retrieval = sub.add_parser("retrieval")
    retrieval.add_argument("--runs", type=int, default=1)
    retrieval.add_argument(
        "--modes", nargs="+", choices=["dense", "hybrid", "hybrid_rerank"], default=["dense"]
    )
    gen = sub.add_parser("generate-suite")
    gen.add_argument("--n", type=int, default=150)
    gen.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    configure_logging(json=Settings().log_json)
    handlers = {
        "triage": cmd_triage,
        "tool-use": cmd_tool_use,
        "retrieval": cmd_retrieval,
        "rag": cmd_rag,
        "generate-suite": cmd_generate,
    }
    handler = handlers[args.command]
    raise SystemExit(asyncio.run(handler(args)))
