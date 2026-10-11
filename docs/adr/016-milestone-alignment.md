# D16: Milestone alignment

**Status:** Accepted · **Date:** 2026-10-11 · **Supersedes:** the "full platform from M1" part of [D5](005-hosting.md)

## Context
The project is assessed strictly against the course milestones M1–M8. D5 provisioned the full Azure platform (APIM, Container Apps, Entra) in M1, although the M1 brief requires only ticket parsing. LLD-1 placed `SupportTicket` as a dataclass, while the M1 brief names a Pydantic model. D10 keeps write tools away from agents, while the M2 brief gives a single agent refund/replace tools.

## Decision
1. **Each milestone delivers exactly its brief line**; components are scheduled into the milestone whose brief needs them ([milestone plan](../02-milestone-plan.md)). Enhancements are additive and never replace a brief requirement.
2. **`SupportTicket` is a frozen Pydantic model** in the domain. CLAUDE.md is amended to allow Pydantic in the domain as a validation library (no I/O, no framework coupling).
3. **M2**: the single agent has refund/replace tools that pass through a deterministic guard in code (cap, paid amount, idempotency). **M5** moves execution to a code step after the risk gate, reaching the D10 end state.
4. **Infrastructure arrives when needed**: Foundry (M1), PostgreSQL (M2), Qdrant (M3), MCP server and Logic Apps (M6), Langfuse and APIM AI gateway (M7), Container Apps deployment with APIM API gateway, Entra and Angular (M8).
5. **Provider-agnostic client** demonstrated in M1 with two providers on Foundry: Claude Opus 5.5 (primary) and an Azure OpenAI model.
6. **`milestones/mN/`** folders hold the per-milestone README and demo script.

## Consequences
- Every milestone is demonstrable and assessable on its own.
- The final architecture is unchanged; only its build order changed.
- The M2 → M5 move of write execution from agent tools to code becomes a documented design progression.
