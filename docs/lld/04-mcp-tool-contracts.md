# LLD-4: MCP tool contracts

**Status:** Accepted · **Date:** 2026-10-11 · **Milestones:** M2 (tools), M6 (MCP server), M7 (resilience)

## Table of contents
- [Decisions](#decisions)
- [Read tools](#read-tools)
- [Write tools](#write-tools)
- [Caller context](#caller-context)
- [Error model](#error-model)
- [Resilience](#resilience)
- [External clients](#external-clients)

## Decisions
| # | Decision |
|---|---|
| L4a | **Two endpoints**: `/mcp/read` (scope `tools.read`) and `/mcp/write` (scope `tools.write`, requested only by the execute use case's adapter); enforced by the server |
| L4b | **Signed caller-context token** per turn (5 min; customer ID, ticket ID, channel, turn) sent as a header; verified by the MCP server and forwarded to the Order Platform |
| L4c | **Structured error model** with `code`, `message`, `retryable`; idempotent replays return the original result |
| L4d | **Data minimization**: no phone, email, address or payment details in tool outputs; free-text fields wrapped as `UntrustedText` by the ShopSense adapter |
| L4e | **Streamable HTTP, stateless** |
| L4f | **Resilience in the MCP server**: timeouts, limited retries, circuit breaker |
| L4g | **External MCP clients**: read endpoint only, via APIM, with the customer's Entra login; write tools never exposed externally |
| L4h | **Schemas and error codes in `libs/contracts`**, versioned; ShopSense validates every response |

All amounts are integers in paise. Customer and ticket identity are never tool arguments.

## Read tools
`/mcp/read` — callable by the Order-Actions agent.

| Tool | Input | Output |
|---|---|---|
| `list_my_orders` | `limit` (≤ 10) | order_no, placed_at, status, total_paise, item names |
| `get_order` | `order_no` | items (sku, name, category, is_accessory, qty, paid_paise, refunded_paise), status, payment method type, delivered_at |
| `track_shipment` | `order_no` | carrier, awb, status, promised_date, delivered_at, last 5 scan events |
| `get_refund_status` | `order_no` | refunds: amount_paise, status, created_at, expected settlement window |
| `calculate_refund` | `order_no`, `item_sku`, `reason` | refundable_paise, paid_paise, already_refunded_paise, breakdown (incl. shipping-fee refundability). Pure calculation |

## Write tools
`/mcp/write` — callable only by the execute use case.

| Tool | Input | Requirements |
|---|---|---|
| `issue_refund` | order_no, item_sku, amount_paise, reason, idempotency_key, approval_grant? | Grant required above ₹5,000 or when the risk gate required approval |
| `create_replacement` | order_no, item_sku, reason, idempotency_key, approval_grant? | Grant required when item value > ₹5,000 |
| `cancel_order` | order_no, reason, idempotency_key | Order not yet shipped |
| `issue_goodwill_credit` | amount_paise (≤ 50,000), reason, idempotency_key | |
| `raise_carrier_trace` | order_no, idempotency_key | |

## Caller context
| Field | Source |
|---|---|
| customer_id | Verified Entra token (chat) or verified sender (email) |
| ticket_id, turn | Orchestrator |
| channel | Channel endpoint |
| exp | Issue time + 5 minutes |

Signed with a Key Vault key (`TokenSigner` port), verified by the MCP server, forwarded to the Order Platform, which checks ownership on every call.

## Error model
| Code | Meaning | Retryable |
|---|---|---|
| `NOT_FOUND` | Missing or not owned by this customer (indistinguishable) | No |
| `VALIDATION_ERROR` | Malformed input | No |
| `NOT_ALLOWED` | Business rule (already shipped, fully refunded, …) | No |
| `APPROVAL_REQUIRED` | Above cap without a valid grant | No |
| `GRANT_INVALID` | Grant expired, used, or mismatched | No |
| `DUPLICATE_REQUEST` | Same idempotency key, different content | No |
| `ORDER_SYSTEM_UNAVAILABLE` | Breaker open or Order Platform down | Yes |
| `TIMEOUT` | Order Platform too slow | Yes |

## Resilience
| Setting | Value |
|---|---|
| Timeout (reads / writes) | 3 s / 5 s |
| Retries | Max 2, retryable errors only; writes only with the same idempotency key |
| Circuit breaker | Opens after 5 failures in 30 s; open for 30 s; one half-open test call |

## External clients
Claude Desktop or VS Code can connect to the read endpoint through APIM with the customer's Entra login (demonstrates M6 cross-channel reuse). Write tools are never exposed outside the Container Apps environment.
