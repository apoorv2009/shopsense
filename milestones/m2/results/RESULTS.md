# M2 — Evidence of results

> **Brief:** Single agent with tools: mock order-lookup API, mock refund/replace API, shipping-tracker API, refund-amount calculator.

**Run date:** 2026-10-11 · **Platform:** Azure Database for PostgreSQL (Central US, `order_platform`, Entra auth) and Azure AI Foundry (`gpt-4.1-mini`) · **Code:** see the M2 commit on `main`

## Files in this folder
| File | What it proves |
|---|---|
| `demo_output.txt` | Live demo: six scenarios (track, small refund, large refund held for approval, replacement, injection with an inflated refund, missing order number) with tool calls and results |
| `m2_tool_use_azure-openai_run1.json` … `run3.json` | Tool-use evaluation, 31 scenarios, three independent runs: per-case checks, tools called, writes, outcome, safety checks |

## Summary
| Metric | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Accuracy (right tools, arguments and outcome) | 96.8% | 96.8% | 96.8% |
| Safety violations | 0 | 0 | 0 |
| Failing case | U19 | U19 | U19 |

Full analysis: [`../README.md`](../README.md#results). Known miss U19 is described there.

## How to reproduce
```bash
uv run uvicorn order_platform.entrypoints.api:app --port 8001     # Order Platform
uv run python milestones/m2/demo.py > milestones/m2/results/demo_output.txt
uv run shopsense-eval tool-use --runs 3                           # reseeds before each run
```
