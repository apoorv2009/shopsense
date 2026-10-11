# M7 — Evidence of results

> **Brief:** LangFuse tracing of ticket-resolution flows; reliability hardening for order-system API flakiness (retries, fallback to human queue, circuit breaker).

**Platform:** Order Platform (order_platform database, fault injection enabled by an admin token); MCP server (circuit breaker, retries); ShopSense API (LangGraph, Postgres checkpoints, outbox in the shopsense database); local JSONL trace

## Files in this folder
| File | What it proves |
|---|---|
| `demo_output.txt` | The outage step by step: a refund waits for a reviewer; the outage opens the breaker; a new ticket is parked; an approval during the outage is queued; the worker settles it; the ticket reads "resolved"; the trace shows every step with masked content |
| `m7_resilience.json` | The scripted outage: transient phase, sustained outage (breaker states and call outcomes), parked ticket, approved refund during the outage, drain result, refunded amount, gates |

## Summary
| Gate | Result |
|---|---|
| Breaker opens under a sustained outage | PASS |
| Ticket parked for a human during the outage | PASS |
| Approved refund queued during the outage | PASS |
| Refunded exactly once after recovery | PASS (149,900 paise, equal to the amount paid) |
| No approved action lost | PASS (0 pending at the end) |
| Breaker closes after recovery | PASS |
| Transient 50% errors: reads that succeeded | 3 of 10 (breaker tripped during the phase; see analysis) |

Analysis and known gaps: [`../README.md`](../README.md#results).

## How to reproduce
```bash
uv run shopsense-eval resilience
uv run python milestones/m7/demo.py > milestones/m7/results/demo_output.txt
```
