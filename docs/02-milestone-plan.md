# Milestone Plan (M1–M8)

The project is assessed milestone by milestone against the course brief. **Each milestone delivers exactly what its brief line states**, demonstrable on its own from `milestones/mN/`. Design components are scheduled into the milestone whose brief creates the need ([D16](adr/016-milestone-alignment.md)); anything beyond the brief is listed as an enhancement and never replaces a brief requirement.

## Table of contents
- [Mandatory components](#mandatory-components)
- [M1 Ticket parsing](#m1-ticket-parsing)
- [M2 Single agent with tools](#m2-single-agent-with-tools)
- [M3 Memory and policy index](#m3-memory-and-policy-index)
- [M4 Production RAG](#m4-production-rag)
- [M5 LangGraph workflow](#m5-langgraph-workflow)
- [M6 Multi-agent team and MCP](#m6-multi-agent-team-and-mcp)
- [M7 Tracing and reliability](#m7-tracing-and-reliability)
- [M8 Evaluation, guardrails, packaging](#m8-evaluation-guardrails-packaging)
- [Per-milestone submission](#per-milestone-submission)

## Mandatory components
| Brief component | Delivered in | Design |
|---|---|---|
| Ticket Triage Agent | M1 (parser), M6 (agent) | [LLD-5](lld/05-agent-designs.md) |
| Policy RAG Agent | M3–M4 (retrieval), M6 (agent) | [LLD-6](lld/06-rules-engine-and-retrieval.md) |
| Order-Actions Agent (refund/replace/track tools) | M2 (single agent), M6 (team) | [LLD-4](lld/04-mcp-tool-contracts.md), [LLD-7](lld/07-order-platform-api.md) |
| Escalation Reviewer Agent | M6 | [LLD-5](lld/05-agent-designs.md) |
| Per-customer interaction memory | M3 | [D9](adr/009-conversation-and-memory.md), [LLD-3](lld/03-data-models.md) |
| Guardrails against unauthorized high-value refunds | M2 (tool guard), M5 (approval interrupt), M8 (cap + grants) | [D10](adr/010-mcp-server-and-tool-safety.md), [D12](adr/012-guardrails.md) |

## M1 Ticket parsing
**Status:** ✅ Done (2026-10-11): mean field accuracy 95–96% over 3 runs of 170 tickets; injection, legal and safety recall 100%; both vendors pass the golden set. Execution plan: [plans/m1.md](plans/m1.md) · Demo: [`milestones/m1`](../milestones/m1/README.md).

**Brief:** *Parse support tickets into a validated Pydantic SupportTicket object (issue type, order ID, sentiment, urgency) via a provider-agnostic client.*

| | |
|---|---|
| Deliverables | Pydantic `SupportTicket` (frozen); `LLMClient` port; LLM gateway with two model vendors on Foundry (OpenAI `gpt-4.1-mini`, Meta `Llama-3.3-70B-Instruct`; Claude adapter available where quota exists); `TriageTicket` use case (random-ID delimiters, one retry, fail closed); triage prompt v1 |
| Data | 20-ticket golden set; ~150 noisy tickets generated from Bitext intents |
| Infrastructure | Foundry model deployments only |
| Demo | Showcase tickets parsed live; same ticket parsed by both providers; field-accuracy table |
| Acceptance | ruff, mypy `--strict`, pytest pass; triage accuracy ≥ 85%; injection/legal/safety flag recall 100% |
| Enhancements | Regex injection screen; `UntrustedText`; token metering |

## M2 Single agent with tools
**Status:** ✅ Done (2026-10-11): tool-use suite 96.8% over 3 runs (31 cases), zero safety violations; one known miss (U19) recorded. Execution plan: [plans/m2.md](plans/m2.md) · Demo: [`milestones/m2`](../milestones/m2/README.md).

**Brief:** *Single agent with tools: mock order-lookup API, mock refund/replace API, shipping-tracker API, refund-amount calculator.*

| | |
|---|---|
| Deliverables | Order Platform API (mock) with PostgreSQL and seed data; single Order-Actions agent with tools `get_order`, `list_my_orders`, `track_shipment`, `calculate_refund`, `request_refund`, `request_replacement` |
| Safety at M2 | Refund/replace tools pass through a **deterministic guard in code** (cap ₹5,000, amount ≤ paid, idempotency); above the cap returns "pending human approval" instead of executing |
| Infrastructure | PostgreSQL Flexible Server (`order_platform`) |
| Demo | Track an order; small refund executes; large refund held for approval |
| Acceptance | Tool-use suite: right tool, right arguments; no refund above cap executes |

## M3 Memory and policy index
**Status:** ✅ Done (2026-10-11): 14 policy documents indexed (44 chunks); retrieval hit@4 97%, MRR@10 0.858 (dense baseline); memory recall and write-back live. Execution plan: [plans/m3.md](plans/m3.md) · Demo: [`milestones/m3`](../milestones/m3/README.md). Qdrant Container App deferred to M8 packaging.

**Brief:** *Persistent per-customer memory (past tickets, preferences) + a Qdrant index over returns/shipping/warranty policy documents.*

| | |
|---|---|
| Deliverables | `shopsense` DB: `ticket_history`, `customer_profiles`; memory loader and writer (anti-poisoning rule); 14 policy documents with rules blocks; ingestion to Qdrant (dense vectors) and the rules table |
| Infrastructure | Qdrant (Container App, ephemeral storage, rebuilt by ingestion), `shopsense` database, Foundry embeddings |
| Demo | Returning customer recognised; policy question answered from retrieved sections |
| Acceptance | Memory recall tests; retrieval baseline on the retrieval suite |

## M4 Production RAG
**Status:** ✅ Done (2026-10-11): eligibility 24/24 by the rules engine; retrieval hit@4 100% and MRR@10 0.887 with hybrid + rerank (dense baseline 97% / 0.858); 0 numbers in delivered replies outside the cited text; groundedness mean 5.0 (own LLM judge). Trap precision@1 is 73% in every mode (reported). Plan: [plans/m4.md](plans/m4.md) · Demo: [`milestones/m4`](../milestones/m4/README.md).

**Brief:** *Production RAG over policy docs with hybrid search/reranking; evaluate groundedness so the assistant never invents a return window or refund amount.*

| | |
|---|---|
| Deliverables | Sparse vectors + RRF fusion; reranker; rules engine decides, RAG cites; consistency check; groundedness evaluation (Foundry evaluator) + numeric fabrication check |
| Demo | Conflicting category windows answered correctly with citations; dense vs hybrid vs hybrid+rerank comparison |
| Acceptance | Retrieval precision on conflict traps; numeric fabrication = 0; groundedness score reported |

## M5 LangGraph workflow
**Status:** ✅ Done (2026-10-11): LangGraph graph with a deterministic risk gate; approval `interrupt()` for amounts above ₹5,000 and angry customers; Postgres checkpoints survive a process restart; routing suite 11/11 with the write gate passing. Plan: [plans/m5.md](plans/m5.md) · Demo: [`milestones/m5`](../milestones/m5/README.md).

**Brief:** *LangGraph workflow: triage → policy-check → action execution → conditional routing (auto-resolve low-risk, human-approval interrupt for high refunds or angry-customer sentiment), with checkpointing.*

| | |
|---|---|
| Deliverables | LangGraph graph (adapter) over domain use cases; router and risk gate (code); execution moves from agent tools to a code step (D10); `interrupt()` for approval; Postgres checkpointer; approval resume via CLI |
| Demo | Low-risk ticket auto-resolves; high refund pauses; angry customer pauses; resume after approval |
| Acceptance | Routing suite; checkpoint round-trip; no write without passing the risk gate |

## M6 Multi-agent team and MCP
**Brief:** *Multi-agent team (Triage, Policy RAG, Order-Actions, Escalation Reviewer) with an MCP server exposing order/refund/shipping mock APIs so the same tools work across chat and email channels.*

| | |
|---|---|
| Deliverables | Four agents as graph nodes; Escalation Reviewer; MCP server (`/mcp/read`, `/mcp/system`, signed caller context); chat channel and email channel (Logic App on a support mailbox → inbound endpoint; replies in-thread and via queue) |
| Infrastructure | MCP server Container App, Logic Apps, Storage queue |
| Demo | Same ticket via chat and via email reaches the same decision; email refund always goes to approval |
| Acceptance | Channel-parity suite; agents cannot reach system tools |

## M7 Tracing and reliability
**Brief:** *LangFuse tracing of ticket-resolution flows; reliability hardening for order-system API flakiness (retries, fallback to human queue, circuit breaker).*

| | |
|---|---|
| Deliverables | Langfuse traces per ticket turn (masked); timeouts, retries, circuit breaker in the MCP server; human-queue fallback; outbox for approved writes; fault injection in the Order Platform |
| Enhancements | Application Insights; APIM AI gateway in front of Foundry |
| Demo | Inject faults → retries and breaker visible in trace → ticket parked → faults off → outbox completes |
| Acceptance | Resilience suite: breaker opens; no approved action lost |

## M8 Evaluation, guardrails, packaging
**Brief:** *Golden eval set of 20 tickets including angry, ambiguous, and prompt-injection cases; guardrails cap auto-approved refund amounts and block policy fabrication; FastAPI packaging with a demo chat endpoint.*

| | |
|---|---|
| Deliverables | Golden set (20) and red-team set run ×3; refund-cap guardrail (risk gate + Order Platform money gate + signed approval grants); fabrication guard (composer placeholders + output guard); FastAPI packaging with demo chat endpoint (SSE) |
| Enhancements | Prompt Shields; photo evidence (vision); Container Apps + APIM API gateway + Entra deployment; Angular customer chat and reviewer console |
| Demo | Golden-set results; angry customer + large refund held; injection blocked; chat endpoint demo |
| Acceptance | Zero-tolerance gates hold in all 3 runs; triage ≥ 85% |

## Per-milestone submission
Each `milestones/mN/` folder contains a README (brief line, what was built, how to run, results) and a demo script. The course requires milestone-wise code, a deck of at most 10 slides, and a demo video of at most 10 minutes.
