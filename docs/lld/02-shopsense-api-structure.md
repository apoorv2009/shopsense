# LLD-2: Repository layout and ShopSense API structure

**Status:** Accepted · **Date:** 2026-10-11

## Table of contents
- [Decisions](#decisions)
- [Repository layout](#repository-layout)
- [ShopSense API layers](#shopsense-api-layers)
- [Ports](#ports)
- [Use cases](#use-cases)
- [API endpoints](#api-endpoints)
- [Processes](#processes)

## Decisions
| # | Decision |
|---|---|
| L2a | **Monorepo** with `services/`, `libs/`, `frontend/`, `infra/`, `evals/`, `data/`, `docs/` |
| L2b | **Share contracts only** (`libs/contracts`: approval-grant format, MCP tool schemas, error codes); each service owns its own domain |
| L2c | **uv workspace**: one lock file; each service is its own package with its own dependencies |
| L2d | **Clean Architecture** inside each service: `domain/`, `application/` (ports, use cases, prompts), `adapters/`, `entrypoints/`. An agent = use case + prompt + output schema |
| L2e | **Prompts as versioned files** in `application/prompts/<agent>/`; prompt version recorded in every trace |
| L2f | **Hand-written composition root** (`entrypoints/composition.py`), fully typed |
| L2g | **REST v1 endpoints**; chat replies streamed with **server-sent events** (progress events, then final reply) |
| L2h | **Outbox worker as a separate process** from the same image, deployed as its own Container App |

## Repository layout
```
shopsense/
  services/
    shopsense_api/
    order_platform/
    mcp_server/
  libs/
    contracts/
  frontend/
  infra/
  evals/
  data/
  docs/
  CLAUDE.md
  pyproject.toml          # uv workspace root
  .github/workflows/ci.yml
```

## ShopSense API layers
```
services/shopsense_api/
  src/shopsense_api/
    domain/
      state/              # TicketState and its sections
      ticket/             # SupportTicket, IssueType, RiskFlag, OrderId
      values/             # Money, UntrustedText, identifiers
      routing/            # router (pure function)
      risk/               # risk gate rules (pure functions)
      policy/             # rules engine (pure functions)
      exceptions.py
      events.py
    application/
      ports/              # Protocols (see below)
      use_cases/          # one per workflow step
      prompts/            # <agent>/v<n>.md
    adapters/
      llm/                # Foundry / Anthropic clients, LLM gateway (routing, fallback, metering)
      graph/              # LangGraph builder, state mapper, checkpointer, interrupts
      http/               # FastAPI routers, Pydantic request/response models, SSE
      mcp/  qdrant/  postgres/  safety/  evaluation/  identity/  queue/  telemetry/
    entrypoints/
      api.py              # web app
      worker.py           # outbox worker
      composition.py      # dependency wiring
      settings.py
  tests/
    unit/  integration/  e2e/
```
Dependency rule: `entrypoints → adapters → application → domain`. LangGraph, FastAPI, SQLAlchemy and SDKs appear only in `adapters/` and `entrypoints/`.

## Ports
| Port | Implemented by (adapter) |
|---|---|
| `LLMClient` | LLM gateway over Foundry (Claude), with provider fallback |
| `OrderTools` | MCP client (read tools for agents; write tools for the execute use case) |
| `PolicyRetriever` | Qdrant hybrid search + reranker |
| `PolicyRulesRepository` | Postgres rules table |
| `CustomerMemoryRepository` | Postgres |
| `TicketRepository` | Postgres |
| `AuditLog` | Postgres (append-only) |
| `OutboxRepository` | Postgres |
| `TokenSigner` | Key Vault key: approval grants and caller-context tokens ([LLD-4](04-mcp-tool-contracts.md#caller-context)) |
| `SafetyChecker` | Content Safety Prompt Shields + regex screen |
| `GroundednessEvaluator` | Foundry evaluator |
| `IdentityDirectory` | Microsoft Graph (registered senders, customer IDs) |
| `ReplyQueue` | Azure Storage queue |
| `Clock`, `IdGenerator` | System clock / UUIDv7 (fakes in tests) |

## Use cases
| Use case | Writes section | Agent? |
|---|---|---|
| Screen input | `input_guard` | No |
| Triage ticket | `ticket` | Triage agent |
| Load customer context | `customer_context` | No |
| Route ticket | `route` | No |
| Evaluate policy | `policy_findings` | Policy RAG agent |
| Propose action | `proposed_action` | Order-Actions agent |
| Evaluate risk | `risk` | No |
| Review case | `review` | Escalation Reviewer agent |
| Record approval | `approval` | No (human) |
| Execute action | `execution` | No |
| Compose reply | `reply` | LLM step |
| Guard output | `output_guard` | No |
| Finalize turn | `turn_history`, memory, audit | No |

## API endpoints
| Endpoint | Caller | Purpose |
|---|---|---|
| `POST /v1/chat/messages` | Customer | Send a message; SSE stream of progress events and the final reply |
| `GET /v1/tickets`, `GET /v1/tickets/{id}` | Customer | My tickets, status, replies |
| `POST /v1/email/inbound` | Logic App | Inbound email |
| `GET /v1/approvals` | Reviewer | Approval queue |
| `GET /v1/approvals/{ticket_id}` | Reviewer | Case view: summary, policy, risk reasons, timeline |
| `POST /v1/approvals/{ticket_id}/decision` | Reviewer | Approve or reject |
| `GET /health/live`, `GET /health/ready` | Container Apps | Probes |

## Processes
| Process | Entrypoint | Container App |
|---|---|---|
| API | `entrypoints/api.py` | `shopsense-api` |
| Outbox worker | `entrypoints/worker.py` | `shopsense-worker` (same image) |
