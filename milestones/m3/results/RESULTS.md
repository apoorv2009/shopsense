# M3 — Evidence of results

> **Brief:** Persistent per-customer memory (past tickets, preferences) + a Qdrant index over returns/shipping/warranty policy documents.

**Run date:** 2026-10-11 · **Platform:** Azure AI Foundry (`text-embedding-3-small`, `gpt-4.1-mini`), Azure Database for PostgreSQL (`shopsense`), Qdrant (embedded, local disk)

## Files in this folder
| File | What it proves |
|---|---|
| `demo_output.txt` | Returning-customer recall, agent with context, memory write-back, cited policy answers, one hand-off |
| `m3_retrieval_dense_run1.json` | Retrieval baseline: 31 questions, the section returned for each, rank of the first acceptable section |

## Summary
| Metric | Value |
|---|---|
| Policy documents / section chunks indexed | 14 / 44 |
| Re-ingestion on unchanged corpus | 0 documents re-indexed (idempotent) |
| Retrieval hit@4 | 97% (30 of 31) |
| Retrieval MRR@10 | 0.858 |

Analysis: [`../README.md`](../README.md#results).

## How to reproduce
```bash
uv run shopsense-ingest
uv run shopsense-eval retrieval --runs 1
uv run python milestones/m3/demo.py > milestones/m3/results/demo_output.txt
```
