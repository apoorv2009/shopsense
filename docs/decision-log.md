# Decision Log

Every architecture decision is recorded as an ADR in [`adr/`](adr/). Status values: **Accepted**, **Proposed** (under discussion), **Superseded**.

## Table of contents
- [Decisions](#decisions)
- [ADR template](#adr-template)

## Decisions
| # | Title | Status | Date |
|---|---|---|---|
| [D1](adr/001-platform-strategy.md) | Platform strategy: course stack + Azure AI Foundry | Accepted | 2026-10-10 |
| [D2](adr/002-quality-bar.md) | Quality bar: portfolio-grade | Accepted | 2026-10-10 |
| [D3](adr/003-service-decomposition.md) | Service decomposition: 3 services | Accepted | 2026-10-10 |
| [D4](adr/004-gateways.md) | API gateway and AI gateway | Accepted | 2026-10-10 |
| [D5](adr/005-hosting.md) | Hosting: Azure Container Apps for all milestones | Accepted | 2026-10-10 |
| [D6](adr/006-data-stores.md) | Data stores | Accepted | 2026-10-10 |
| [D7](adr/007-agent-topology.md) | Agent topology and shared state | Accepted | 2026-10-11 |
| [D8](adr/008-channels-ui-identity.md) | Channels, UI, identity and email trust | Accepted | 2026-10-11 |
| [D9](adr/009-conversation-and-memory.md) | Conversation model and long-term memory | Accepted | 2026-10-11 |
| [D10](adr/010-mcp-server-and-tool-safety.md) | MCP server design and tool safety | Accepted | 2026-10-11 |
| [D11](adr/011-policy-as-data.md) | Policy as data | Accepted | 2026-10-11 |
| [D12](adr/012-guardrails.md) | Guardrail map and risk gate | Accepted | 2026-10-11 |
| [D13](adr/013-resilience-and-observability.md) | Resilience and observability | Accepted | 2026-10-11 |
| D14 | Evaluation strategy and data sources | Not started | |

## ADR template
```
# D<n>: <title>
Status · Date
## Context        — the problem and forces
## Options        — each with pros and cons
## Decision       — what we chose
## Consequences   — what follows, good and bad
```
