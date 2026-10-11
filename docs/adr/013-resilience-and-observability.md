# D13: Resilience and observability

**Status:** Accepted · **Date:** 2026-10-11

## Table of contents
- [Context](#context)
- [Failure inventory](#failure-inventory)
- [Resilience patterns](#resilience-patterns)
- [Observability](#observability)
- [Decisions](#decisions)
- [Consequences](#consequences)

## Context
M7 requires retries, a circuit breaker and fallback to a human queue when the order system is flaky, plus Langfuse tracing. Every dependency can fail, so behaviour is decided for each one.

## Failure inventory
| Dependency | Failure | Response |
|---|---|---|
| Order Platform | Slow, errors, down | Timeout → retry → circuit breaker → human queue |
| MCP server | Slow, down | Timeout and retry from ShopSense → human queue |
| Model (Foundry via APIM) | Rate limited, overloaded, refusal | APIM failover across deployments → gateway-module provider fallback → human queue |
| Qdrant | Down | Eligibility decisions continue (rules table in Postgres, [D11](011-policy-as-data.md)); replies needing policy text go to a human |
| Content Safety, evaluator | Down | Fail closed → human ([D12](012-guardrails.md)) |
| PostgreSQL | Down | Service unavailable; never act without the audit log |
| Langfuse | Down | Never blocks; traces exported in the background and dropped on failure |
| Email (Logic App, mailbox) | Delay | Storage queue holds replies ([D8](008-channels-ui-identity.md)) |

## Resilience patterns
| Pattern | Design |
|---|---|
| Timeouts | On every outbound call; overall budget per chat turn (~30 s) |
| Retries | Max 3; exponential backoff with jitter; only for transient errors (timeout, 429, 503); writes retried only with the same idempotency key |
| Circuit breaker | Opens after repeated failures (e.g. 5 in 30 s); cool-down (e.g. 30 s); half-open test call |
| Fallback for reads | Ticket parked in the human queue with a holding reply |
| Fallback for approved writes | **Outbox pattern**: the approved action is recorded in the `shopsense` DB in the same transaction as the approval; a background worker executes and retries until confirmed; idempotency keys make retries safe |
| Fault injection | Internal-only switch in the Order Platform for added latency and error rate (M7 demo) |

## Observability
| | Langfuse | Application Insights (OpenTelemetry) |
|---|---|---|
| Question answered | What did the AI do, and why? | Is the system healthy, and where is it slow? |
| Captures | One trace per ticket turn; spans per workflow step; model calls with tokens and cost; tool calls; retrieved chunks; risk-gate decision; evaluator scores | Requests, inter-service dependencies, errors, latency; APIM and Container Apps logs |
| Used by | AI engineering, evaluation, reviewer-console timeline | Operations and alerting |

- **Correlation:** one W3C `traceparent` propagated ShopSense → MCP server → Order Platform. Audit-log rows store the Langfuse trace ID and the Application Insights operation ID.
- **Dashboards:** auto-resolve vs escalation rate by reason, approval wait time, refund value auto vs human-approved, guardrail hits, cost per ticket, p95 latency, breaker state.
- **Alerts:** breaker open, fail-closed rate spike, cost spike.

## Decisions
| # | Question | Decision |
|---|---|---|
| D13a | Where does the circuit breaker live? | **MCP server**, around Order Platform calls (protects every MCP client); ShopSense keeps timeouts and retries on its MCP calls |
| D13b | Failure fallback | Human queue for failed reads; **outbox with retry worker** for approved writes |
| D13c | Fault injection | Internal-only latency and error-rate switch in the Order Platform |
| D13d | Observability split | Langfuse for AI traces; Application Insights for system telemetry; linked by trace ID |
| D13e | Personal data in traces | **Masked** (emails, phones, addresses) before export |

## Consequences
- No approved refund is lost during an order-system outage.
- The M7 demo can show retries, the breaker opening, human-queue fallback and outbox completion on a live trace.
- Masking keeps personal data out of third-party tooling, at some cost to debugging convenience.
