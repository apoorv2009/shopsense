# D3: Service decomposition — 3 services

**Status:** Accepted · **Date:** 2026-10-10

## Context
We must decide how many deployable services to build. The 4 agents share one conversation state. The order system is, in the real world, owned by another team, and M7 requires resilience against its flakiness. M6 requires an MCP server so the same tools serve multiple channels.

## Options
**1. Modular monolith** (one FastAPI app; MCP server as a separate process)
- Pros: simplest; lowest latency; one log stream.
- Cons: order system is in-process, so M7 retries and circuit breaker would be faked; no boundary between "our AI product" and "the company's order system".

**2. Microservices** (gateway, orchestrator, one service per agent, order, RAG, memory, approvals)
- Pros: independent scaling and deployment.
- Cons: agents sharing LangGraph state would serialise it across the network every step; heavy infrastructure for one developer; boundaries drawn around code modules rather than ownership.

**3. Three services along real-world boundaries**
| Service | Role |
|---|---|
| ShopSense API | Channels, LangGraph workflow, 4 agents, memory, guardrails, approvals |
| Order Platform API (mock) | Orders, shipments, refunds; financial invariants; fault injection |
| MCP server | Order operations as MCP tools for any AI client |
- Pros: every boundary has a real reason (ownership, failure mode, protocol); M7 resilience wraps a real network call; M6 tools reusable by any MCP client; refund cap enforced in the order system too.
- Cons: three processes to run and deploy.

## Decision
**Option 3.** Agents stay in one process (ShopSense API) and share state cheaply.

## Consequences
- The Order Platform can be made deliberately slow or failing for the M7 demo.
- The Order Platform enforces financial invariants independently of ShopSense ([D10](010-mcp-server-and-tool-safety.md)).
