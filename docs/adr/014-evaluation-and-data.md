# D14: Evaluation strategy and data sources

**Status:** Accepted (D14f proposed) · **Date:** 2026-10-11

## Table of contents
- [Context](#context)
- [Data sources](#data-sources)
- [Evaluation suites](#evaluation-suites)
- [Decisions](#decisions)
- [D14f: intent taxonomy (proposed)](#d14f-intent-taxonomy-proposed)
- [Consequences](#consequences)

## Context
Each milestone must be provably working, and the brief names specific data sources and traps. Ticket text is attacker-controlled, so evaluation weights prompt injection heavily.

## Data sources
| Data | Decision |
|---|---|
| Support intents | **Bitext retail e-commerce dataset** (CDLA-Sharing 1.0), downloaded; see [data/README.md](../../data/README.md) |
| Order data | **Generated Indian data** (carriers, ₹ amounts, abuse flags, fixture customers/orders for golden tickets); Olist not used (non-commercial licence, Kaggle login, Brazilian context) |
| Policy documents | **14 generated documents** with planted category conflicts and machine-readable rules blocks ([D11](011-policy-as-data.md)) |
| Tickets | **Generated from Bitext intents with noise**: 1 in 8 angry, 1 in 6 missing order reference, several above the refund cap, ≥2 legal, ≥2 injection, ≥1 safety; Hinglish and typos |
| Anger calibration | **Optional** ~50-tweet sample from the Customer Support on Twitter corpus, licence checked first |
| Course `generate.py` | To be checked in the course portal; use and extend if available |

## Evaluation suites
| Suite | Size | Measures | Grading | Milestone |
|---|---|---|---|---|
| Triage | ~150 generated + Bitext sample | Field accuracy | Exact match | M1 |
| Tool use | ~30 scenarios | Right tool, arguments, proposed action | Exact match | M2 |
| Retrieval | ~40 labelled questions | Hit rate at k, ranking quality, conflict-trap precision | Exact match on doc and section | M3, M4 |
| Rules engine | Exhaustive boundaries | Deterministic correctness | Unit tests | M3, M4 |
| Groundedness and fabrication | Retrieval + golden replies | Support by cited text; numeric fabrication = 0 | Foundry evaluator + numeric check | M4, M8 |
| Routing | Golden expected routes | Auto / approval / escalate / ask | Exact match | M5 |
| Channel parity | Same tickets via chat and email | Same decision (email refunds → approval) | Exact match | M6 |
| Resilience | Fault-injection scenarios | Breaker opens; no approved action lost; human-queue fallback | Scripted assertions | M7 |
| Red team | ~25 injection variants | 0 successful attacks | Code checks | M8 |
| Golden | 20 hand-labelled tickets | End to end | All of the above | M8 |

## Decisions
| # | Question | Decision |
|---|---|---|
| D14a | Tooling | **Langfuse datasets and experiments** (runs linked to traces), Foundry evaluators for groundedness, pytest for deterministic tests; results exported to markdown for the deck |
| D14b | Release gates | **Zero tolerance**: unauthorized refunds, numeric fabrications, successful injections, missed safety/legal escalations. Targets (no hard gate): triage accuracy ≥ 85% |
| D14c | Run variance | Golden and red-team sets run **3 times**; report mean and spread; zero-tolerance metrics must hold in all runs |
| D14d | CI | **Deterministic tests on every push**; LLM evaluation on demand before milestone demos |
| D14e | Downloads | Bitext downloaded (2026-10-11); Twitter corpus downloaded by the user if used |

## D14f: intent taxonomy (proposed)
The downloaded Bitext retail dataset has **13 categories and 46 intents**, not the "27 intents across ORDER, DELIVERY, PRODUCT, REFUND and FEEDBACK" described in the brief (that description matches Bitext's separate *customer-support* dataset). Proposal: map the in-scope Bitext intents onto ShopSense issue types, and route the rest to a polite out-of-scope reply.

| ShopSense issue type | Bitext intents |
|---|---|
| order_status | track_order |
| cancel_order | cancel_order |
| change_order | change_order |
| track_shipment | track_delivery |
| delivery_delay | delivery_issue |
| damaged_or_defective | damaged_delivery, product_issue |
| wrong_item | wrong_item |
| missing_item | missing_item |
| return_request | return_product, return_product_online, return_product_in_store |
| replacement_request | exchange_product, exchange_product_in_store |
| refund_request | request_refund |
| refund_status | refund_status |
| policy_question | return_policy, refund_policy, delivery_time, shipping_costs, payment_methods |
| payment_issue | payment_issue |
| complaint | submit_feedback |
| request_human | human_agent |
| warranty_claim, product_safety | *(not in Bitext; generated)* |
| out_of_scope | ACCOUNT, CART, APP_WEBSITE, STORE, SALES, USER, product availability/information, request_invoice, pay, customer_service, product feedback/ideas |

## Consequences
- Evaluation results are reproducible (seeded data, frozen reference date) and traceable to individual runs.
- The taxonomy gains `missing_item`, `request_human` and `out_of_scope` routes (pending D14f).
