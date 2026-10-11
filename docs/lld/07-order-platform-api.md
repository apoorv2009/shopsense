# LLD-7: Order Platform API

**Status:** Accepted · **Date:** 2026-10-11 · **Milestones:** M2 (orders, tools), M7 (fault injection), M8 (grant hardening)

## Table of contents
- [Decisions](#decisions)
- [Endpoints](#endpoints)
- [Identity verification](#identity-verification)
- [Money gate](#money-gate)
- [Fault injection](#fault-injection)
- [Seed data](#seed-data)
- [Settlement simulation](#settlement-simulation)
- [Structure](#structure)

## Decisions
| # | Decision |
|---|---|
| L7a | **Internal REST API**; every POST requires an `Idempotency-Key` header |
| L7b | **`/mcp/system` (code-only toolset)** replaces `/mcp/write`: write tools plus sensitive reads such as `get_customer_risk_profile`; agents never hold `tools.system` ([LLD-4](04-mcp-tool-contracts.md)) |
| L7c | **Zero-trust identity**: the MCP server forwards the original signed caller-context token; the Order Platform verifies it again, plus the MCP server's managed-identity token |
| L7d | **Money gate in the Order Platform**: no-grant actions only ≤ ₹5,000 **and** channel = chat; email always needs a grant; full grant verification; single-use grants; paid-amount check |
| L7e | **Admin fault-injection endpoint** with automatic expiry, internal only, separate admin permission, audited |
| L7f | **Seeded generator + golden fixtures**, all dates relative to a configurable anchor date |
| L7g | **Simulated settlement**: approved → processing → processed after a payment-method-dependent delay |
| L7h | **Clean Architecture** (domain, application, adapters, entrypoints) |

## Endpoints
| Endpoint | Backs |
|---|---|
| `GET /v1/orders`, `GET /v1/orders/{order_no}` | `list_my_orders`, `get_order` |
| `GET /v1/orders/{order_no}/shipment` | `track_shipment` |
| `GET /v1/orders/{order_no}/refunds` | `get_refund_status` |
| `POST /v1/orders/{order_no}/refund-quote` | `calculate_refund` (no side effects) |
| `GET /v1/customers/me/risk-profile` | `get_customer_risk_profile` (system only): abuse flag, return rate, tier |
| `POST /v1/refunds` | `issue_refund` |
| `POST /v1/replacements` | `create_replacement` |
| `POST /v1/orders/{order_no}/cancellation` | `cancel_order` |
| `POST /v1/goodwill-credits` | `issue_goodwill_credit` |
| `POST /v1/carrier-traces` | `raise_carrier_trace` |
| `POST /admin/faults`, `GET /admin/faults` | Fault injection (admin) |
| `GET /health/live`, `GET /health/ready` | Probes |

## Identity verification
On every request:
1. Validate the caller's managed-identity token (audience = Order Platform; caller = MCP server).
2. Validate the forwarded caller-context token (ShopSense signature, expiry).
3. Use only the token's `customer_id`; every order lookup is scoped to it (not owned → `NOT_FOUND`).

## Money gate
Refunds and replacements:

| Case | Rule |
|---|---|
| No grant | Allowed only if amount ≤ ₹5,000 **and** caller-context channel = chat |
| With grant | Signature valid; not expired; ticket, order, item, action match; amount ≤ grant maximum; grant unused |
| Always | `refunded_paise + amount ≤ unit_price_paise × qty` under a row lock |
| Single use | Grant ID recorded in the same transaction as the refund (unique constraint) |

## Fault injection
| Field | Meaning |
|---|---|
| `latency_ms` | Added delay |
| `error_rate` | 0.0–1.0 share of requests returning 503 |
| `scope` | reads · writes · both |
| `duration_s` | Faults switch off automatically after this time |

Internal ingress only; admin permission required; every change written to the log.

## Seed data
- Generator: Faker (`en_IN`), fixed seed; customers, products (incl. accessories), orders, shipments with scan events, refunds.
- Golden fixtures: customers `C0001`–`C0010`, orders from `ORD-100001`, one per scenario (over-cap laptop, abuse-flagged customer, stuck shipment, lost parcel, pressure-cooker burn, serum rash, damaged rice for photo check, …).
- Dates relative to an anchor date: evaluation environments freeze the anchor and ShopSense's `Clock` to the same date; the demo environment anchors to today.
- Run via the `seed` entrypoint.

## Settlement simulation
| Payment method | Delay to `processed` |
|---|---|
| UPI | Short (simulated 1–3 business days) |
| Net banking | Medium (3–5) |
| Cards, COD bank transfer | Longer (5–7) |

Delays are compressed for the demo by configuration.

## Structure
| Layer | Contents |
|---|---|
| Domain | Order, OrderItem, Refund, Replacement, Money, invariants, grant-verification rules |
| Application | Use cases, ports (repositories, token verifier, clock) |
| Adapters | FastAPI routes, SQLAlchemy repositories, token verification, fault middleware |
| Entrypoints | `api.py`, `seed.py`, composition root |
