# D7: Agent topology and shared state

**Status:** Accepted · **Date:** 2026-10-11

## Context
The brief requires 4 agents: Triage, Policy RAG, Order-Actions, Escalation Reviewer. The key question is who decides what happens next. Ticket text is attacker-controlled, and the system moves money.

## Options
**1. LLM supervisor** decides which agent runs next
- Pros: flexible; popular in demos.
- Cons: routing controlled by an LLM that reads attacker text (an injection could skip escalation); non-deterministic paths make evaluation unstable; more calls; hard to explain decisions.

**2. Fixed pipeline**: every ticket goes through every agent in order
- Pros: predictable; cheap.
- Cons: wasteful; cannot ask for missing information; agents become plain functions.

**3. Deterministic backbone with agentic nodes**: code controls flow, LLMs do the work inside steps
- Pros: safety decisions never made by an LLM; autonomy where it adds value (tool loop, retrieval, case review); stable routes and explainable decisions; maps directly to LangGraph nodes, conditional edges, `interrupt()` and checkpoints.
- Cons: less flexible for unforeseen ticket types; router and risk rules must be designed carefully.

### Shared information (D7b)
- **(a) Shared typed state** (`TicketState`): each agent reads and writes its own section.
- **(b) Message passing** between agents in natural language.

## Decision
**Option 3** with **shared typed state (a).**

Flow: input guard → Triage agent → load memory → router (code) → Policy RAG agent → Order-Actions agent (proposes) → risk gate (code) → execute (code) or Escalation Reviewer agent + human approval → response composer → output guard → memory and audit write. See the [HLD workflow](../01-hld.md#5-ticket-workflow).

## Consequences
- Agents **propose**; code **executes** ([D10](010-mcp-server-and-tool-safety.md)).
- The risk gate reads structured fields, never parses free text.
- A new ticket type requires a new route in code.
