# M1 — Evidence of results

> **Brief:** Parse support tickets into a validated Pydantic `SupportTicket` object (issue type, order ID, sentiment, urgency) via a provider-agnostic client.

**Run date:** 2026-10-11 · **Platform:** Azure AI Foundry, East US 2 (resource `ais-shopsense-dev-yuegx3`) · **Prompt:** `triage/v2` · **Code:** commit `79f15c9`

## Table of contents
- [Files in this folder](#files-in-this-folder)
- [Summary](#summary)
- [How to reproduce](#how-to-reproduce)

## Files in this folder
| File | What it proves |
|---|---|
| `demo_output.txt` | Live demo: showcase tickets parsed into validated `SupportTicket` objects; the same ticket parsed by two vendors (OpenAI, Meta) |
| `m1_triage_all_azure-openai_run1.json` … `run3.json` | Full evaluation, 170 tickets (20 golden + 150 generated from Bitext), `gpt-4.1-mini`, three independent runs: per-case checks, parsed tickets, field accuracy, flag recall, gate status |
| `m1_triage_golden_azure-openai_run1.json` | Golden set (20) on OpenAI `gpt-4.1-mini` |
| `m1_triage_golden_foundry-llama_run1.json` | Golden set (20) on Meta `Llama-3.3-70B-Instruct` (provider-agnostic client) |

## Summary
| Metric | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Mean field accuracy (target ≥ 85%) | 95% | 96% | 96% |
| All fields correct | 78% | 80% | 79% |
| Prompt-injection recall | 13/13 | 13/13 | 13/13 |
| Legal-threat recall | 8/8 | 8/8 | 8/8 |
| Product-safety recall | 7/7 | 7/7 | 7/7 |
| Errors | 0 | 0 | 0 |
| Gates | PASS | PASS | PASS |

| Golden set (20) | Mean field accuracy | All fields correct | Gates |
|---|---|---|---|
| OpenAI `gpt-4.1-mini` | 100% | 100% | PASS |
| Meta `Llama-3.3-70B-Instruct` | 98% | 90% | PASS |

Full analysis and lessons learned: [`../README.md`](../README.md#results).

## How to reproduce
```bash
uv run python milestones/m1/demo.py                              # demo_output.txt
uv run shopsense-eval triage --suite all --runs 3                # run1..run3 JSON
uv run shopsense-eval triage --suite golden --provider foundry-llama
```
Requires the M1 Foundry deployment ([`infra/m1`](../../../infra/m1)) and `az login`.
