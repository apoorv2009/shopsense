# M4 — Production RAG

> **Brief:** Production RAG over policy docs with hybrid search/reranking; evaluate groundedness so the assistant never invents a return window or refund amount.

## Table of contents
- [What was built](#what-was-built)
- [How it maps to the brief](#how-it-maps-to-the-brief)
- [Design choices](#design-choices)
- [Setup](#setup)
- [Run](#run)
- [Results](#results)
- [Known gaps](#known-gaps)

## What was built
| Piece | Location |
|---|---|
| Rules engine: candidates by conditions, overrides, specificity, tie detection (fails closed), IST day counting, evidence gate | `services/shopsense_api/src/shopsense_api/domain/policy/rules_engine.py` |
| Grounding checks: numeric fabrication, sparse keyword vectors | `.../domain/policy/grounding.py` |
| Hybrid retrieval: dense, sparse, reciprocal rank fusion (k = 60), reranking | `.../application/use_cases/hybrid_search.py` |
| Local cross-encoder reranker (fastembed ONNX) | `.../adapters/policy/fastembed_reranker.py` |
| Qdrant index with named dense and sparse vectors (`policy_chunks_v2`) | `.../adapters/policy/qdrant_index.py` |
| `DecideReturn`: rules engine decides, cited section must match the corpus hash | `.../application/use_cases/decide_return.py` |
| `AnswerPolicyQuestion`: citations must be retrieved, numbers must appear in the cited text | `.../application/use_cases/answer_policy.py` |
| Groundedness judge (LLM, scored 1–5) | `.../application/use_cases/judge_groundedness.py`, prompt `judge/v1.md` |
| Corpus changes so that precedence is unambiguous (goodwill and cancellation are not return rules; damage rules override the windows they replace) | `data/policies/` |
| Evaluation: 24 decision cases with boundary and trap facts; 31 retrieval questions in three modes; 12 open questions | `evals/data/decisions.jsonl`, `retrieval.jsonl`, `open_policy.jsonl`, `shopsense-eval rag` |
| Demo | `milestones/m4/demo.py` |

## How it maps to the brief
| Brief | Implementation |
|---|---|
| Production RAG over policy docs | Hybrid retrieval over 14 documents (44 section chunks), with the answer path checked in code |
| Hybrid search and reranking | Dense + sparse fused with RRF, then a cross-encoder over the top 20 |
| Evaluate groundedness | Judge score on every delivered answer; supported share reported |
| The assistant never invents a return window or refund amount | Eligibility and windows come from the rules engine, not the model. Model answers are blocked when a number is not in the cited text |

## Design choices
| Decision | Choice | Why |
|---|---|---|
| Who decides eligibility? | Rules engine in code. RAG only explains and cites | An LLM must never decide a window or amount |
| Precedence | Overrides first, then most conditions, and a tie is an error | Makes "which window applies" a deterministic, testable rule |
| Hybrid fusion | Two Qdrant queries fused in code with RRF | Qdrant local mode does not run server-side prefetch fusion. The result is the same, and it is easy to test |
| Reranker | Local cross-encoder (`Xenova/ms-marco-MiniLM-L-6-v2`) | Cohere via Foundry is not deployed on the free trial. The port allows swapping it later |
| Consistency check | Index hash must equal corpus hash for the cited section | A stale index escalates rather than cites old text |
| Judge | Our own LLM judge via the gateway | The Azure AI evaluation SDK needs a Foundry project and key-based auth. This is a deviation (see Known gaps) |

## Setup
Same as M3 (`shopsense-ingest` already done). Rebuild the index once for the hybrid layout:
```bash
uv run shopsense-ingest --rebuild
```
The first rerank downloads the cross-encoder model (about 90 MB) into the fastembed cache.

## Run
```bash
uv run shopsense-eval rag                 # decisions + three retrieval modes + open questions
uv run python milestones/m4/demo.py       # rules, comparison, cited answers
```

## Results
Raw evidence: [`results/`](results/RESULTS.md).

### Eligibility decisions (24 cases; deterministic)
| Result | |
|---|---|
| Correct | **24 of 24** |
| Covers | Window boundaries (day 15 eligible, day 16 not; accessory day 7 eligible, day 8 not; apparel 45), precedence over the general 30-day rule, opened versus unopened beauty, groceries with and without damage, damage within 48 hours (boundary at 48 h versus 48 h plus one minute), and an unknown category falling back to 30 days |

### Retrieval (31 questions)
| Mode | hit@4 | MRR@10 | Trap precision@1 |
|---|---|---|---|
| Dense | 97% | 0.858 | 73% |
| Hybrid (RRF) | 97% | 0.861 | 73% |
| Hybrid + rerank | **100%** | **0.887** | 73% |

**Trap precision@1 (honest reading).** Category questions are where the general 30-day policy competes with a category window. In every mode the general section ranks first for four of the 15 such questions. The category section is still in the top 4 in all of them, and the eligibility decision comes from the rules engine, so the decision stays correct (24 of 24). The gap is in how the explanation is ordered. Improving it needs a category-specific boost, which is a follow-up and not part of this result.

### Open questions (12)
| Result | |
|---|---|
| Answered with citations | 10 |
| Handed off | 2 (Mars: no policy covers it; one answer that invented "20 days" was blocked by the number check) |
| Numbers in delivered replies that are not in the cited text | **0** |
| Attempts blocked by the number check | 1 |
| Groundedness (judge, 1–5) | mean **5.0**, supported 100% of delivered answers |

Caveat: the judge is a model from the same family as the answerer, so it can be lenient. Its score is a measurement, not an independent audit.

## Known gaps
- **Foundry groundedness evaluator not used.** The judge is our own prompt on the gateway (R4-7). Switching to `azure-ai-evaluation` needs a Foundry project and Entra-compatible auth.
- **Cohere reranker not deployed.** The local cross-encoder is used; the Foundry Cohere deployment is deferred.
- **Trap precision@1 unchanged across modes** (see Results).
- **Rules precedence ties are detected at decision time.** Load-time detection (LLD-6) can be added to `validate_corpus`.
- **Photo verification is not implemented.** Evidence is an input (`photo_verified`); the vision check is M6/M8.
