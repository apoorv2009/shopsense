# M5 — Evidence of results

> **Brief:** LangGraph workflow: triage → policy-check → action execution → conditional routing (auto-resolve low-risk, human-approval interrupt for high refunds or angry-customer sentiment), with checkpointing.

**Platform:** LangGraph 1.2 with `AsyncPostgresSaver` (shopsense database, Azure Database for PostgreSQL, Entra auth); Order Platform (order_platform database); Azure AI Foundry (`gpt-4.1-mini` for triage)

## Files in this folder
| File | What it proves |
|---|---|
| `demo_output.txt` | Each step runs as a separate `shopsense-workflow` process: auto-resolve, pause for a large refund, approval from another process, angry-customer pause, rejection with no write, injection hand-off |
| `m5_routing_run1.json` | Routing suite: for each ticket, expected and actual outcome, route and write count, and the reply |

## Summary
| Metric | Result |
|---|---|
| Routing suite | 11 / 11 correct |
| Write gate | PASS (writes only in tickets expecting a write) |
| Checkpoint round trip | PASS: paused in process A, resumed from Postgres in process B |
| Unit tests | 19 pass (workflow), 179 pass (all shopsense unit tests) |

Analysis and known gaps: [`../README.md`](../README.md#results).

## How to reproduce
```bash
uv run shopsense-eval routing --runs 1
uv run python milestones/m5/demo.py > milestones/m5/results/demo_output.txt
```
