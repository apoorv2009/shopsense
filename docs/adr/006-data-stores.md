# D6: Data stores

**Status:** Accepted · **Date:** 2026-10-10

## Context
Container Apps have no permanent disk, so file databases such as SQLite are not viable. Data to place: orders/customers/shipments/refunds (relational, transactional), customer memory, LangGraph checkpoints, approvals and audit log, and policy vectors.

## Options
**1. One Azure Database for PostgreSQL Flexible Server (2 databases) plus Qdrant**
- Pros: transactions for refunds; official LangGraph Postgres checkpointer; one managed server; burstable tier is enough.
- Cons: cost while idle; migration scripts needed.

**2. Azure SQL Database (serverless)**
- Pros: auto-pause can be cheaper.
- Cons: no official LangGraph checkpointer; cold starts after pause.

**3. Cosmos DB for everything except vectors**
- Pros: serverless pricing; JSON fits checkpoints.
- Cons: orders and refunds are relational and transactional; no official checkpointer.

### Where Qdrant runs
- **(a) Qdrant Cloud free tier**: managed; but outside the Azure subscription.
- **(b) Qdrant as a Container App with Azure Files storage**: everything in one subscription; we operate it; file shares are slower (fine at demo scale).

## Decision
**Option 1 with Qdrant (b).**
| Store | Contents | Accessed by |
|---|---|---|
| PostgreSQL `order_platform` | Customers, products, orders, shipments, refunds | Order Platform only |
| PostgreSQL `shopsense` | Tickets, memory, checkpoints, approvals, audit log, policy rules table | ShopSense API only |
| Qdrant (Container App, ephemeral storage; see amendment) | Policy chunks, dense and sparse vectors | ShopSense API |
| Key Vault | Secrets, approval-grant signing key | All, via managed identity |

## Amendment (2026-10-11, M3)
Qdrant does not support network file systems, and Azure Files is SMB, so option (b) risks a corrupted index. Qdrant now runs as a Container App with **ephemeral storage**, scale 0–1, external ingress with an API key (the ShopSense API runs locally until M8). The index is derived data: the policy files in git and the rules table in PostgreSQL are the source of truth, and an idempotent ingestion step rebuilds it in seconds; demo and evaluation scripts ingest first. Tests use the Qdrant client's in-process local mode. Plan: [plans/m3.md](../plans/m3.md).

## Consequences
- Each service owns its database; no cross-service database access.
- No secrets in code or environment files.
