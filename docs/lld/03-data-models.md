# LLD-3: Data models

**Status:** Accepted · **Date:** 2026-10-11

## Table of contents
- [Decisions](#decisions)
- [Column conventions](#column-conventions)
- [order_platform database](#order_platform-database)
- [shopsense database](#shopsense-database)
- [Qdrant collection](#qdrant-collection)

## Decisions
| # | Decision |
|---|---|
| L3a | **SQLAlchemy 2.0 (typed, async) + Alembic**, migrations per service (in place for `order_platform` since M2 and `shopsense` since M3); ORM models only in `adapters/db/`, mapped to domain dataclasses |
| L3b | **UUIDv7 internal primary keys** plus human-readable public numbers (`ORD-123456`, `TKT-1042`, `C0001`); public numbers never used for joins |
| L3c | **Column conventions**: money as `amount_paise BIGINT` + `currency CHAR(3)` with `CHECK (amount_paise >= 0)`; all timestamps `TIMESTAMPTZ` in UTC; statuses as enums or checked text |
| L3d | **Customer return rate computed by a view**, never stored |
| L3e | **`ticket_messages` table** for UI and reviewer, in addition to workflow checkpoints |
| L3f | **Risk counters computed by query**, never stored as counters |
| L3g | **Embeddings: Azure OpenAI `text-embedding-3-small` via Foundry** (through the AI gateway); sparse keyword vectors computed locally |

## Column conventions
| Concern | Rule |
|---|---|
| Primary key | `id UUID` (v7) |
| Public identifier | `*_no TEXT UNIQUE` with format check |
| Money | `*_paise BIGINT NOT NULL CHECK (>= 0)`, `currency CHAR(3) DEFAULT 'INR'` |
| Time | `TIMESTAMPTZ`, UTC |
| Status | Enum or `CHECK (status IN (...))` |

## order_platform database
Owned by the Order Platform; no other service connects to it.

| Table | Columns | Notes |
|---|---|---|
| `customers` | id, customer_no, name, email, phone, city, tier, abuse_flag, created_at | |
| `products` | id, sku, name, category, is_accessory, price_paise, warranty_months | `is_accessory` drives the 7-day electronics accessory rule |
| `orders` | id, order_no, customer_id, status, payment_method, total_paise, placed_at | |
| `order_items` | id, order_id, product_id, qty, unit_price_paise, refunded_paise | Refunds tracked per item |
| `shipments` | id, order_id, carrier, awb, status, promised_date, delivered_at | |
| `shipment_events` | id, shipment_id, status, location, scanned_at | Scan history for tracking |
| `refunds` | id, order_item_id, amount_paise, reason, status, approval_tier, grant_id UNIQUE, idempotency_key UNIQUE, created_at | Unique `grant_id` makes each approval grant single-use |
| `replacements` | id, order_item_id, reason, status, grant_id UNIQUE NULL, idempotency_key UNIQUE, created_at | |
| `goodwill_credits` | id, customer_id, amount_paise, reason, idempotency_key UNIQUE, created_at | Max ₹500 enforced in code and by check |
| `carrier_traces` | id, shipment_id, status, idempotency_key UNIQUE, created_at | |
| `cancellations` | id, order_id, reason, idempotency_key UNIQUE, created_at | |
| `idempotency_records` | key, request_hash, response, created_at | Same key + same request → original response; same key + different request → rejected |
| `customer_return_rates` (view) | customer_id, delivered_orders, returned_orders, return_rate | Computed from orders and refunds |

**Refund integrity:** in one transaction, lock the `order_items` row (`SELECT … FOR UPDATE`), check `refunded_paise + amount ≤ unit_price_paise × qty`, insert the refund, update `refunded_paise`. Concurrent refunds cannot both pass.

## shopsense database
Owned by the ShopSense API (and its outbox worker).

| Table | Columns | Notes |
|---|---|---|
| `tickets` | id, ticket_no, customer_id, channel, status, order_no, created_at, closed_at, reopen_count | status: open, awaiting_customer, awaiting_approval, awaiting_system, resolved, closed |
| `ticket_messages` | id, ticket_id, role, body, channel, email_message_id, created_at | Display copy of the conversation |
| `attachments` | id, ticket_id, turn, blob_path, content_type, size_bytes, sha256, source (chat/email), uploaded_at | Photo evidence; blob in Azure Blob Storage |
| `approvals` | id, ticket_id, turn, status, approver_tier, reasons, requested_at, decided_by, decided_at, comment, grant_id | status: pending, approved, rejected, expired |
| `outbox` | id, ticket_id, action, idempotency_key UNIQUE, status, attempts, next_attempt_at, last_error | Approved and auto-approved writes |
| `audit_log` | id, ticket_id, turn, event_type, actor, payload, langfuse_trace_id, operation_id, created_at | Append-only: application role has INSERT/SELECT only |
| `customer_profiles` | customer_id, preferred_language, preferred_refund_method, preferred_channel | Allowed values only |
| `ticket_history` | customer_id, ticket_id, issue_type, order_no, outcome, sentiment, resolved_at, summary | Long-term memory |
| `policy_documents` | doc_id, version, content_hash, effective_date, ingested_at | |
| `policy_rules` | rule_id, doc_id, version, section, category, conditions, window_days, outcome, precedence, effective_from | Rules table ([D11](../adr/011-policy-as-data.md)) |
| LangGraph checkpoint tables | managed by the library | Workflow state ([LLD-1](01-ticket-state.md)) |

**Risk counters (queries):**
- Automatic refunds in the last 30 days: executed `outbox` refund actions with no approval, per customer.
- Contacts per order in the last 7 days: customer messages on tickets for that order.

## Qdrant collection
`policy_chunks`

| Part | Design |
|---|---|
| Dense vector | `text-embedding-3-small` (cosine) |
| Sparse vector | BM25-style keyword vector (local), for hybrid search |
| Payload | doc_id, version, section, title, category, applies_to, rule_ids, text, content_hash |
| Chunking | One chunk per policy section; document title prefixed to each chunk |
| Re-index trigger | Document `content_hash` changes |

Reranker choice: [LLD-6](../decision-log.md#low-level-design).
