# LLD-1: TicketState

**Status:** Accepted · **Date:** 2026-10-11 · **Milestones:** M1 (SupportTicket), M5 (full state)

## Table of contents
- [Purpose](#purpose)
- [Decisions](#decisions)
- [Layer placement](#layer-placement)
- [Sections](#sections)
- [SupportTicket](#supportticket)
- [Trust model](#trust-model)
- [Money](#money)
- [Turn lifecycle](#turn-lifecycle)
- [Retention](#retention)
- [Invariants to test](#invariants-to-test)

## Purpose
`TicketState` is the single shared record for one ticket. The orchestrator and every agent read and write it; it is checkpointed so tickets can pause for human approval and resume. It is also the source for the reviewer console's case view and the audit log.

## Decisions
| # | Decision |
|---|---|
| L1a | **Sectioned state with strict ownership**: each step writes only its own section; enforced by tests |
| L1b | **Per-turn sections cleared at each new customer turn**; a compact `turn_history` record is kept; whole-ticket sections persist |
| L1c | **Sections are frozen dataclasses in the domain layer**; Pydantic only at the edges (LLM structured output, API bodies, MCP payloads); LangGraph is an adapter that maps its state to and from domain objects |
| L1d | **Money is an integer number of paise** (`Money` value object); never float or decimal |
| L1e | **Trust labels**: text from customers or tools is wrapped as `UntrustedText`; fields extracted from it are untrusted; the risk gate and execution use trusted fields only |
| L1f | **Raw text retained 90 days after ticket closure**; then checkpoints are deleted, keeping the audit log and system-derived summary |

## Layer placement
| Layer | TicketState-related contents |
|---|---|
| Domain | `TicketState` and section dataclasses, `SupportTicket`, `Money`, `UntrustedText`, enums, domain exceptions |
| Application | Use cases that take the current state and return **only their own section** |
| Adapters | LangGraph state schema and mappers; Pydantic models for LLM output and API payloads; Postgres checkpointer |

## Sections
| Section | Owner (only writer) | Contents | Lifetime |
|---|---|---|---|
| `meta` | Channel endpoint | ticket ID, thread ID, channel (chat/email), verified customer ID, turn number, Langfuse trace ID, App Insights operation ID, received time | Whole ticket |
| `messages` | Channel endpoint (customer), Composer (assistant) | Visible conversation only; customer text stored as `UntrustedText` | Whole ticket, append-only |
| `input_guard` | Input guard | Regex result, Prompt Shields result, service status | Per turn |
| `ticket` | Triage agent | `SupportTicket` | Whole ticket, updated each turn |
| `customer_context` | Memory loader | History summaries, preferences, risk counters, abuse flag, tier | Refreshed each turn |
| `route` | Router | Path and reason code | Per turn |
| `policy_findings` | Policy RAG agent + rules engine | Rules decision (eligible, window days, days since delivery, outcome, rule IDs, rules version), cited clauses, consistency-check result | Per turn |
| `evidence` | Evidence checker (vision) | Attachment refs, per-photo result (matches_claim, confidence, observations) ([LLD-6](06-rules-engine-and-retrieval.md#photo-evidence)) | Per turn |
| `proposed_action` | Order-Actions agent | Action type, order, item, amount (`Money`, from `calculate_refund`), reason, facts from read tools | Per turn |
| `risk` | Risk gate | Decision (auto / approval / escalate / ask), approver tier, all matched rules with reasons | Per turn |
| `review` | Escalation Reviewer agent | Case summary, recommendation, key evidence | Per turn |
| `approval` | Human (reviewer API) | Approved/rejected, reviewer ID, comment, time, grant ID | Per turn |
| `execution` | Execute step | Outbox record ID, idempotency key, result, Order Platform reference | Per turn |
| `reply` | Composer | Draft, final reply, regeneration count | Per turn |
| `output_guard` | Output guard | Numeric check, forbidden-claims check, groundedness score, pass/fail | Per turn |
| `turn_history` | Orchestrator | One compact record per finished turn: route, decision, action, outcome | Whole ticket, append-only |

## SupportTicket
| Field | Type | Trust | Notes |
|---|---|---|---|
| `issue_type` | `IssueType` enum ([D14f](../adr/014-evaluation-and-data.md#d14f-intent-taxonomy)) | Derived | Includes `missing_item`, `request_human`, `out_of_scope` |
| `secondary_issues` | list of `IssueType` | Derived | Multiple-issue tickets |
| `order_id` | `OrderId` (`ORD-` + 6 digits) or none | **Untrusted until ownership confirmed** | Never invented; malformed → none |
| `product_category_hint` | `ProductCategory` or none | **Untrusted** | Real category comes from the Order Platform product record |
| `claimed_amount` | `Money` or none | **Untrusted** | Informational only; never used in decisions |
| `sentiment` | positive / neutral / frustrated / angry | Derived | Risk-gate input |
| `urgency` | low / medium / high / critical | Derived | |
| `flags` | set of `RiskFlag` (legal_threat, social_media_threat, product_safety, prompt_injection_suspected, abusive_language, multiple_issues) | Derived | Risk-gate input; union with deterministic screens |
| `language` | en / hinglish / other | Derived | Reply style |
| `summary` | short neutral text, length-limited | Derived | Only free text allowed into long-term memory |

*Derived* = produced by the triage model under schema constraints; used for routing, combined with deterministic checks.

## Trust model
| Trust level | Examples | May drive decisions? |
|---|---|---|
| **Trusted** | Verified customer ID, Order Platform records, rules-engine results, risk-gate output, human approval | Yes |
| **Derived** | Triage enums and flags | Routing only, combined with deterministic checks |
| **Untrusted** | `UntrustedText` (customer messages, email bodies, tool free-text), `order_id` before ownership check, `claimed_amount`, `product_category_hint` | **No** |

`UntrustedText` is a domain value object: it can be shown to a model only inside delimited tags, and it cannot be passed where a trusted type is expected.

## Money
- `Money` is a frozen value object holding an integer amount in paise and the currency (INR).
- Arithmetic and comparisons only between `Money` values; no float conversion anywhere in the pipeline.
- Display formatting (₹54,990.00) happens only at the edges.

## Turn lifecycle
1. A new customer message arrives on an existing thread.
2. The orchestrator appends the previous turn's outcome to `turn_history`.
3. All per-turn sections are cleared.
4. `messages` is appended; `customer_context` is refreshed; triage updates `ticket` (e.g. the order ID is now provided).
5. The workflow runs from the input guard as usual.

This prevents a stale proposal or approval from an earlier turn being acted on.

## Retention
- Checkpoints and raw `messages` are kept for 90 days after the ticket closes, then deleted.
- The audit log and system-derived summaries are kept.
- Telemetry is masked at export ([D13e](../adr/013-resilience-and-observability.md#decisions)).

## Invariants to test
1. Each use case returns only its own section (ownership).
2. The risk gate and execute step accept no untrusted types (enforced by types and `mypy --strict`).
3. Starting a new turn clears every per-turn section.
4. `Money` never converts to float; caps compare in paise.
5. `summary` respects its length limit; no other free text reaches memory.
6. A checkpoint round-trip (save, load) reproduces an identical state.
