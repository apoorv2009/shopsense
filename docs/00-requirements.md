# Requirements

## Table of contents
- [Purpose](#purpose)
- [Actors](#actors)
- [Channels](#channels)
- [Functional scope](#functional-scope)
- [Non-functional requirements](#non-functional-requirements)
- [Success criteria](#success-criteria)
- [Constraints](#constraints)
- [Out of scope](#out-of-scope)

## Purpose
Build a multi-agent assistant for e-commerce customer support that classifies and resolves tickets, answers policy questions from RAG, executes order actions through tools, and escalates complex or emotional cases to human agents.

The system is built for two audiences: course graders (milestone-wise functionality) and a professional portfolio (architecture quality). The quality bar is portfolio-grade (see [D2](adr/002-quality-bar.md)).

## Actors
| Actor | Description | Authenticates via |
|---|---|---|
| Customer | Raises tickets about orders, refunds, shipping and policy | Entra ID user, role `customer`, with a `customer_id` attribute |
| Human reviewer | Approves or rejects escalated cases; sees case summaries | Entra ID user, role `reviewer` |
| Logic App (system) | Delivers inbound email to the API and sends email replies | Managed identity |
| Eval runner (system) | Replays the golden ticket set against the deployed system | Service credential |

## Channels
| Channel | Entry point | Notes |
|---|---|---|
| Chat | Angular customer portal → APIM → ShopSense API | Logged-in customer, multi-turn |
| Email | Support mailbox → Logic App → APIM → ShopSense API | Registered and DMARC-verified senders only; lower trust ([D8](adr/008-channels-ui-identity.md)) |
| Reviewer console | Angular reviewer area → APIM → ShopSense API | Approval queue, case timeline |
| API / batch | Direct to the API | Evaluation and tests |

## Functional scope
1. **Triage:** parse free-text tickets into a validated `SupportTicket` (issue type, order ID, sentiment, urgency, amount, risk flags).
2. **Multi-turn conversations:** ask the customer for missing information (e.g. order ID) and continue the same ticket.
3. **Policy answers:** answer return, refund, shipping and warranty questions from the policy documents, with citations.
4. **Order actions:** look up orders, track shipments, calculate refunds, issue refunds, create replacements, cancel orders, issue goodwill credit, raise carrier traces. Actions write to the order database, idempotently.
5. **Risk-based routing:** auto-resolve low-risk tickets; pause for human approval on high-value or risky cases; escalate safety, legal and injection cases.
6. **Per-customer memory:** past tickets, preferences and risk counters.
7. **Authorization:** a customer can access only their own orders.
8. **Evaluation:** a golden set of 20 tickets including angry, ambiguous and prompt-injection cases.

## Non-functional requirements
| Quality | Requirement |
|---|---|
| Safety | No refund above the automated cap without human approval, enforced in code at two independent layers |
| Correctness | No invented return windows, amounts or policy rules |
| Security | Ticket text treated as untrusted; no customer can read another customer's data; no secrets in code |
| Resilience | Order-system failures handled with retries, timeouts and a circuit breaker; fall back to the human queue |
| Observability | Every ticket traceable end to end (agent steps, tool calls, model calls, cost) |
| Explainability | Every routing decision has a recorded reason; full audit log |
| Portability | Model provider swappable by configuration |
| Processing model | Synchronous chat; human-approval pauses held in durable checkpoints |
| Scale | Demo scale (tens of concurrent users); architecture must not preclude scale-out |

## Success criteria
Measured on the golden set:
- 0 unauthorized refunds
- 0 invented policy numbers (days or ₹ amounts)
- 100% of injection, legal and product-safety tickets escalated
- Triage accuracy of at least 85%

## Constraints
- Must cover milestones M1–M8 in order; each milestone separately demonstrable.
- Course-named technology: Pydantic, Qdrant, LangGraph, MCP, Langfuse, FastAPI.
- Hosted on Azure (subscription available); same target infrastructure for all milestones.
- Submission: milestone-wise code, a deck of at most 10 slides, and a demo video of at most 10 minutes.

## Out of scope
- Real payment processing (the order platform is a mock with realistic behaviour)
- Production-scale load testing
- Languages other than English and Hinglish
