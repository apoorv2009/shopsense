# M4 — Evidence of results

> **Brief:** Production RAG over policy docs with hybrid search/reranking; evaluate groundedness so the assistant never invents a return window or refund amount.

**Run date:** 2026-10-11 · **Platform:** Azure AI Foundry (`text-embedding-3-small`, `gpt-4.1-mini`), Qdrant (embedded, local disk), fastembed cross-encoder (local)

## Files in this folder
| File | What it proves |
|---|---|
| `demo_output.txt` | Rules decide with citations (four cases), the three retrieval modes side by side, and cited open answers with a groundedness score |
| `m4_rag.json` | Full evaluation: 24 decisions (expected and got), retrieval summaries for three modes, 12 open answers (citations, blocked numbers, recheck, judge verdict), summary |
| `m4_retrieval_dense.json`, `m4_retrieval_hybrid.json`, `m4_retrieval_hybrid_rerank.json` | Per-question ranks for each retrieval mode |

## Summary
| Metric | Result |
|---|---|
| Eligibility decisions correct | 24 / 24 |
| Retrieval hit@4 (dense / hybrid / hybrid + rerank) | 97% / 97% / 100% |
| Retrieval MRR@10 | 0.858 / 0.861 / 0.887 |
| Trap precision@1 (all modes) | 73% |
| Open answers delivered / handed off | 10 / 2 |
| Numbers in delivered replies not found in cited text | 0 |
| Fabrication attempts blocked | 1 |
| Groundedness (judge, 1–5) | mean 5.0; supported 100% |

Analysis and caveats: [`../README.md`](../README.md#results).

## How to reproduce
```bash
uv run shopsense-ingest --rebuild
uv run shopsense-eval rag
uv run python milestones/m4/demo.py > milestones/m4/results/demo_output.txt
```
