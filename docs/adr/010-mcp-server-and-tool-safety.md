# D10: MCP server design and tool safety

**Status:** Accepted · **Date:** 2026-10-11

## Context
The MCP server is where money moves. The design goal is that no LLM, even one fully compromised by prompt injection, can cause an unauthorized action.

## D10a: Build or generate
- **APIM-generated MCP from the REST API:** almost no code; no business validation; doesn't meet the course deliverable.
- **Own MCP server** (Python MCP SDK, HTTP transport, Container App): full control. **Chosen.** Optionally registered in APIM for external MCP clients.

## D10b: Tools and the read/write split
| Read tools | Write tools |
|---|---|
| `list_my_orders`, `get_order`, `track_shipment`, `get_refund_status`, `calculate_refund` (pure) | `issue_refund`, `create_replacement`, `cancel_order`, `issue_goodwill_credit` (≤ ₹500), `raise_carrier_trace` |

**LLM agents can call read tools only.** The Order-Actions agent proposes an action as structured output; the execution step (code) calls write tools after the risk gate and any human approval.

## D10c: Identity is attached by code
- LLM-filled arguments describe **what** (order ID, reason), never **who**.
- Customer ID and ticket ID are attached as call metadata by our code, from the verified token or verified email sender.
- The Order Platform checks ownership on every call; a mismatch returns the same "not found" as a missing order.

## D10d: Approval grants and financial invariants
The Order Platform enforces, independently of ShopSense:
- refund ≤ amount paid
- each item refunded at most once; idempotency key on every write
- **refunds above ₹5,000 require a valid approval grant**

An approval grant is a short-lived (15 minutes) token signed with a Key Vault key, issued by ShopSense only after a human approves. It binds ticket, order, action, maximum amount and approver. The Order Platform verifies the signature before executing.

Separation of responsibility:
- **Order Platform:** financial invariants (always true)
- **ShopSense:** context-dependent risk (anger, channel, abuse flag, legal threats)

## D10e: Service-to-service authentication
- ShopSense API → MCP server → Order Platform with managed-identity tokens; each validates the token audience.
- MCP server and Order Platform use internal ingress only.

## Consequences
- Even with ShopSense fully compromised, no refund above the cap can execute without a human-approved, signed grant.
- External MCP clients (e.g. Claude Desktop) can reuse the tools through APIM, demonstrating M6's cross-channel reuse.
