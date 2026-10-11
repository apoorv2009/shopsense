# D4: API gateway and AI gateway

**Status:** Accepted · **Date:** 2026-10-10

## Context
Two kinds of gateway are relevant. An **API gateway** sits in front of our APIs (authentication, roles, rate limits, routing). An **AI gateway** sits in front of model providers (token limits, failover, usage metrics, caching). Without a central LLM layer, retries, fallback, token accounting and tracing would be duplicated across 4 agents.

## Options for the AI gateway
1. **None**: agents call SDKs directly. Least work; duplicated concerns; hard to swap models.
2. **In-process LLM gateway module**: routing by task, provider fallback, retries, cost metering, tracing and safety hooks in one module. No extra infrastructure; not shareable across apps.
3. **Azure API Management AI gateway**: token rate limits, usage metrics, load balancing, circuit breaking, semantic caching. Enterprise-standard and reusable; extra Azure setup and cost; extra network hop.
4. **Open-source proxy (LiteLLM)**: off the shelf; another container; duplicates option 2 without the Azure story.

## Decision
Build **both gateways with one APIM instance**, plus the in-process module:
| Layer | Responsibility |
|---|---|
| APIM as **API gateway** | Validates Entra ID tokens and roles; passes a trusted customer ID; per-customer rate limits; separates customer and reviewer routes; logging and versioning |
| APIM as **AI gateway** | Token limits per agent and customer, usage metrics, failover across model deployments, circuit breaking, optional semantic caching |
| **In-process LLM gateway module** | Task-based model routing, fallback when the AI gateway is unavailable, Prompt Shields hook, Langfuse spans, cost per ticket |

## Consequences
- Cloud APIM cannot reach a laptop, so services must be hosted in Azure ([D5](005-hosting.md)).
- APIM tier, AI-gateway policy availability per tier, and provisioning time to be verified before choosing the tier.
