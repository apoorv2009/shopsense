# D11: Policy as data

**Status:** Accepted · **Date:** 2026-10-11

## Context
Eligibility, return windows and refund paths depend on policy rules written in documents that humans maintain. The brief requires a Policy RAG agent **and** that the system never invents a return window or amount. The policy corpus deliberately contains conflicting category rules (electronics 15 days, apparel 45, groceries non-returnable, general 30) to test retrieval precision.

## Options
**1. RAG only**: the LLM retrieves policy text and decides eligibility
- Pros: documents are the single source of truth.
- Cons: a retrieval miss gives a confidently wrong window (the planted trap); unreliable date arithmetic and precedence; non-deterministic.

**2. Code only**: rules table in code; RAG for general questions
- Pros: exact and testable.
- Cons: rules duplicated in documents and code; silent drift; RAG agent becomes decorative.

**3. Policy as data, plus RAG for explanation**
Each policy document carries its prose **and** a machine-readable rules block. Ingestion produces text chunks for Qdrant and rows for a versioned rules table.
- Pros: exact decisions and grounded, cited explanations; single source of truth; drift detected automatically.
- Cons: rules blocks to design and maintain; more complex ingestion.

## Decision
**Option 3**, with the rules engine in **ShopSense** (D11b: support policy is owned by support; the Order Platform keeps only financial invariants).

Runtime division of work:
| Step | Done by |
|---|---|
| Product category | Order Platform product record (never the LLM's guess) |
| Days since delivery | Code |
| Applicable rule and precedence | Rules engine (code) |
| Explanation and citation | Policy RAG agent |
| Consistency check (retrieved clause contains the rule's values) | Code; mismatch → escalate |
| Customer reply | Composer agent, numbers only from rules result, tool results and cited text |

## Consequences
- Evaluation measures decision accuracy, groundedness, numeric fabrication (target 0) and retrieval precision (right addendum retrieved).
- RAG still answers questions the rules do not cover (refund timelines, data wiping, general "can I return X?").
