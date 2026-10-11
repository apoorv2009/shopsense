# M6 — Evidence of results

> **Brief:** Multi-agent team (Triage, Policy RAG, Order-Actions, Escalation Reviewer) with an MCP server exposing order/refund/shipping mock APIs so the same tools work across chat and email channels.

**Platform:** MCP server (official `mcp` SDK v1, streamable HTTP, stateless) on localhost; ShopSense API (FastAPI, LangGraph, Postgres checkpoints); Order Platform (order_platform database); Azure AI Foundry for the LLM agents

## Files in this folder
| File | What it proves |
|---|---|
| `demo_output.txt` | The same ticket on two channels (email held for a reviewer, chat resolved); unregistered sender refused; read and system scopes; forged token refused; tools offered to the model |
| `m6_parity_run1.json` | Channel parity: for each ticket, the chat and email decisions (outcome, route, eligibility, rule, amount), the expectation, and the judgement |

## Summary
| Metric | Result |
|---|---|
| Channel parity | 5 / 5 correct |
| Email refunds that reached an automatic write | 0 |
| Read token on the system endpoint | HTTP 403 |
| Forged token on the read endpoint | HTTP 401 |
| Write tools offered to the Order-Actions agent | 0 |

Analysis and known gaps: [`../README.md`](../README.md#results).

## How to reproduce
```bash
uv run shopsense-eval parity --runs 1
uv run python milestones/m6/demo.py > milestones/m6/results/demo_output.txt
```
