# M3 — Memory and policy index

> **Brief:** Persistent per-customer memory (past tickets, preferences) + a Qdrant index over returns/shipping/warranty policy documents.

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
| Policy corpus: 14 documents, each section with a `rules` block (conflicting category windows included) | `data/policies/` |
| Policy domain: documents, sections, rules, chunks; load-time validation (rule values must appear in section text, known conditions, unique IDs, overrides resolve) | `services/shopsense_api/src/shopsense_api/domain/policy/` |
| Customer memory domain: ticket records, preferences (allowed values only), templated summary, `CustomerContext` | `.../domain/memory/model.py` |
| Markdown corpus parser (front matter, numbered sections, JSON rules blocks validated at the edge) | `.../adapters/policy/markdown_corpus.py` |
| Qdrant index (cosine, deterministic point IDs, idempotent re-indexing) | `.../adapters/policy/qdrant_index.py` |
| Foundry embeddings (`text-embedding-3-small`) | `.../adapters/policy/foundry_embedder.py` |
| SQL stores: ticket history, customer profiles, policy documents and rules (`shopsense` database, Alembic baseline) | `.../adapters/db/` |
| Use cases: `IngestPolicies`, `SearchPolicy`, `AnswerPolicyQuestion`, `RecallCustomer`, `RememberTicket` | `.../application/use_cases/` |
| Order-Actions agent receives the trusted customer context as a labelled block | `.../application/agents/order_actions.py` |
| Prompt `policy_answer/v2` (answers only from retrieved sections; hands off when they do not address the question) | `.../application/prompts/policy_answer/` |
| `shopsense-ingest` command (migrates, indexes changed documents only) | `.../entrypoints/cli.py` |
| Retrieval evaluation: 31 labelled questions, hit@4 and MRR@10 | `evals/data/retrieval.jsonl`, `shopsense-eval retrieval` |
| Infrastructure: embedding deployment and `shopsense` database | `infra/m3/main.bicep` |

## How it maps to the brief
| Brief | Implementation |
|---|---|
| Per-customer memory: past tickets | `ticket_history` table; `RememberTicket` writes one templated record per ticket outcome |
| Per-customer memory: preferences | `customer_profiles` with allowed values only (language, refund method, channel) |
| Memory used by the agent | `RecallCustomer` builds a context block of system records; the Order-Actions agent receives it as trusted context |
| Qdrant index over returns, shipping and warranty policies | 14 documents, 44 section chunks, dense vectors in Qdrant |

## Design choices
| Question | Choice | Why |
|---|---|---|
| Who writes the ticket summary? | Code, from a template over system facts (issue type, order, outcome, amount) | Customer text never reaches memory (D9 anti-poisoning). Enforced by construction: `summarize_ticket` takes only enums, an order number and an integer |
| Where does Qdrant run? | Embedded Qdrant on local disk for the demo and evaluation; Container App with ephemeral storage is the deployment target (see Known gaps) | Qdrant does not support network file systems such as Azure Files. The index is derived data, rebuilt by `shopsense-ingest` from the policy files in git |
| Can the answer cite what it did not read? | No. Citations must be a subset of the retrieved sections, otherwise the reply is a hand-off | Grounding is checked in code, not only in the prompt |
| Does an unanswerable question get a guess? | No. Prompt v2 requires the sections to address the question directly. Prompt v1 answered "Do you deliver to Mars?" from the shipping section, which is why v2 exists | Found in the first live demo run and fixed; both versions are kept in the repository |

## Setup
1. Deploy the embedding deployment and the `shopsense` database (uses the M1 Foundry account and the M2 PostgreSQL server):
   ```bash
   az deployment group create -g rg-shopsense-dev-eus2 -f infra/m3/main.bicep
   ```
2. In `.env`, set `SHOPSENSE_DATABASE_URL=postgresql+asyncpg://<user>@psql-shopsense-dev-yuegx3.postgres.database.azure.com:5432/shopsense`, with the Entra user name URL-encoded.
3. Index the policies (creates the schema through migrations, then indexes):
   ```bash
   uv run shopsense-ingest
   ```

## Run
```bash
uv run uvicorn order_platform.entrypoints.api:app --port 8001   # Order Platform (M2)
uv run shopsense-ingest                                          # idempotent
uv run shopsense-eval retrieval --runs 1                         # retrieval baseline
uv run python milestones/m3/demo.py                              # memory + policy demo
uv run pytest                                                    # unit tests
```

## Results
Raw evidence: [`results/`](results/RESULTS.md).

### Retrieval baseline (dense only; M4 must beat this)
| Metric | Value |
|---|---|
| Questions | 31 |
| hit@4 (an acceptable section is in the top 4) | 97% (30 of 31) |
| MRR@10 | 0.858 |
| Miss | R30 "store credit for a late delivery": the goodwill section ranks 6th, behind shipping, cash-on-delivery and damaged-item sections |

### Demo
The demo clears and reseeds a returning customer's history, recalls it, runs the order agent with that context, writes the outcome back, and answers policy questions with citations. See [`results/demo_output.txt`](results/demo_output.txt).

- Recall shows two past tickets and the preferences, all from system records.
- A question with no answer in the policies ("Do you deliver to Mars?") is handed off rather than answered.
- Cash-on-delivery questions cite the three sections that answer them.

## Known gaps
- **Qdrant Container App is not deployed.** The Bicep module is planned for M8 packaging, when the ShopSense API itself is containerised. Until then the index is embedded (local disk), which keeps the demo and evaluation reproducible.
- **Dense retrieval only.** Hybrid search and reranking are M4.
- **Database token lifetime.** The Entra token for the `shopsense` database is fetched once when the process starts (about one hour). Long-running processes need the token refresh that the Order Platform already has.
- **No automated PostgreSQL test for the SQL stores yet.** They are exercised by the live ingestion and the demo; a PostgreSQL integration test is a follow-up.
