# ShopSense — Customer Care & Order Operations Assistant

A multi-agent AI assistant for a mid-size Indian e-commerce marketplace. It triages support tickets, answers policy questions from RAG, executes order actions through tools, and escalates risky or emotional cases to human agents.

IIT Hyderabad course project, Problem Statement 4 (Retail / E-commerce), built across 8 milestones (M1–M8).

> **Status:** design phase. No code yet: the architecture, HLD and LLD are being finalised first and recorded here as architecture decision records (ADRs).

## Table of contents
- [The problem](#the-problem)
- [Design documents](#design-documents)
- [Decisions at a glance](#decisions-at-a-glance)
- [Milestones](#milestones)
- [Technology](#technology)

## The problem
Support agents handle thousands of order, refund and shipping tickets. Most are routine; a few are dangerous: angry customers demanding large refunds, legal threats, product-safety reports, and tickets that try to manipulate the system (prompt injection). ShopSense resolves the routine ones automatically, answers only from the company's policy documents, refuses to be tricked or to give away money, and hands risky cases to a human with a ready-made case summary.

Guiding principle: **LLMs understand and explain; code decides and enforces.**

## Design documents
| Document | Contents |
|---|---|
| [Requirements](docs/00-requirements.md) | Actors, channels, scope, success criteria, constraints |
| [High-level design](docs/01-hld.md) | System context, components, deployment, data, request flows |
| [Decision log](docs/decision-log.md) | Index of every architecture decision and its status |
| [ADRs](docs/adr/) | One record per decision: context, options with pros and cons, decision, consequences |

## Decisions at a glance
| # | Decision |
|---|---|
| [D1](docs/adr/001-platform-strategy.md) | Course stack (LangGraph, Qdrant, MCP, Langfuse, FastAPI) plus Azure AI Foundry, behind our own interfaces |
| [D2](docs/adr/002-quality-bar.md) | Portfolio-grade: every required concept implemented properly |
| [D3](docs/adr/003-service-decomposition.md) | 3 services: ShopSense API, Order Platform API, MCP server |
| [D4](docs/adr/004-gateways.md) | Azure APIM as API gateway and AI gateway, plus an in-process LLM gateway module |
| [D5](docs/adr/005-hosting.md) | Azure Container Apps for every milestone |
| [D6](docs/adr/006-data-stores.md) | One PostgreSQL Flexible Server (2 databases), Qdrant as a Container App, Key Vault |
| [D7](docs/adr/007-agent-topology.md) | Deterministic backbone with agentic nodes; shared typed state |
| [D8](docs/adr/008-channels-ui-identity.md) | Angular SPA, real email via Logic App, Entra ID users; email trust model |
| [D9](docs/adr/009-conversation-and-memory.md) | 1 ticket = 1 workflow thread; structured long-term memory; anti-poisoning rule |
| [D10](docs/adr/010-mcp-server-and-tool-safety.md) | Own MCP server; LLM gets read-only tools; signed approval grants for large refunds |
| [D11](docs/adr/011-policy-as-data.md) | Policy as data: rules engine decides, RAG explains and cites |
| [D12](docs/adr/012-guardrails.md) | Layered guardrail map and risk gate; fail closed |

## Milestones
| # | Scope |
|---|---|
| M1 | Ticket → validated `SupportTicket` through a provider-agnostic client |
| M2 | Single agent with order lookup, refund/replace, shipment tracking and refund calculator tools |
| M3 | Per-customer memory and a Qdrant index over policy documents |
| M4 | Production RAG: hybrid search, reranking, groundedness evaluation |
| M5 | LangGraph workflow with human-approval interrupt and checkpointing |
| M6 | 4-agent team (Triage, Policy RAG, Order-Actions, Escalation Reviewer) and an MCP server, across chat and email |
| M7 | Langfuse tracing; resilience against order-system failures (retries, circuit breaker, human-queue fallback) |
| M8 | 20-ticket golden eval (angry, ambiguous, prompt injection); guardrails; FastAPI packaging with demo chat endpoint |

## Technology
Python, FastAPI, LangGraph, Qdrant, MCP, Langfuse, Pydantic · Azure AI Foundry (Claude), Azure AI Content Safety (Prompt Shields), Azure AI Evaluation · Azure API Management, Container Apps, Database for PostgreSQL, Key Vault, Logic Apps, Static Web Apps, Entra ID · Angular
