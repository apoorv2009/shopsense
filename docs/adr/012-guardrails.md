# D12: Guardrail map and risk gate

**Status:** Proposed · **Date:** 2026-10-11

## Table of contents
- [Context](#context)
- [Guardrail map](#guardrail-map)
- [Risk gate rules](#risk-gate-rules)
- [Open points](#open-points)

## Context
Guardrails decided in D4–D11 are collected into one layered map. Principle: every threat is stopped by at least two independent layers, and the last layer is never an LLM.

## Guardrail map
| # | Layer | Guardrail | Stops | Implemented by |
|---|---|---|---|---|
| 1 | Edge | Token and role validation | Anonymous access; customers on reviewer routes | APIM |
| 2 | Edge | Per-customer rate limits; max request size | Flooding; cost attacks | APIM |
| 3 | Email intake | Registered sender + DMARC pass | Strangers; impersonators | Logic App, then API |
| 4 | Input | Regex injection screen | Known injection phrasing | ShopSense |
| 5 | Input | Prompt Shields | Injection the regex misses | Content Safety |
| 6 | Model | Foundry content filters; token limits | Harmful output; runaway spend | Foundry, APIM |
| 7 | Triage | Ticket isolation in tags; structured output; validation | Model obeying ticket text; malformed output | ShopSense |
| 8 | Tools | Read-only LLM tools; code-attached identity; ownership checks | Unauthorized actions; cross-customer access | MCP server, Order Platform |
| 9 | Decision | Rules engine; policy consistency check | Wrong windows; policy drift | ShopSense |
| 10 | Decision | Risk gate (code) | Risky cases auto-resolved | ShopSense |
| 11 | Execution | Approval grants; cap, paid-amount, no-double-refund; idempotency | Unapproved high-value refunds; double refunds | Order Platform |
| 12 | Output | Numeric fabrication check; forbidden claims | Invented numbers; "refund approved" when not executed; leaking fraud flags or queues | ShopSense |
| 13 | Output | Groundedness evaluation | Unsupported policy claims | Foundry evaluator |
| 14 | Memory | System-derived facts only | Memory poisoning | ShopSense |
| 15 | Audit | Append-only log of decisions, tool calls, approvals, replies | Disputes; supports evaluation | PostgreSQL |

## Risk gate rules
First match wins.

| Priority | Condition | Route |
|---|---|---|
| 1 | Product-safety flag | Escalate: safety queue |
| 2 | Legal, social-media or press threat | Escalate: senior agent |
| 3 | Prompt injection flagged by any layer | Escalate: senior agent |
| 4 | Customer abuse flag | Approval: fraud team |
| 5 | Order ID missing or customer ambiguous | Ask the customer |
| 6 | Policy consistency check failed | Escalate: senior agent |
| 7 | Amount above ₹25,000 | Approval: manager |
| 8 | Amount ₹5,001 to ₹25,000 | Approval: team lead |
| 9 | Angry customer and value above ₹5,000 | Approval: team lead |
| 10 | Email channel with any refund | Approval: team lead |
| 11 | Automatic refund already given in last 30 days | Approval: team lead |
| 12 | Third contact on same issue within 7 days | Escalate: senior agent |
| 13 | Otherwise | Auto-resolve |

Rule 9 is subsumed by rule 8 but kept separately so the recorded reason matches the escalation-triggers policy.

## Open points
| # | Question | Proposed answer |
|---|---|---|
| D12a | Guardrail service unavailable: fail open or closed? | **Fail closed**: route to a human |
| D12b | When does live groundedness evaluation run? | **Only replies making policy claims**; numeric check on every reply |
| D12c | Output guard rejects a reply | **Regenerate once** with feedback; then holding reply and human handoff |
| D12d | Abusive language alone | **No escalation**; polite reply, flag recorded; abuse plus another risk follows normal rules |
