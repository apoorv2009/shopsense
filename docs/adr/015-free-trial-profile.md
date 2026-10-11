# D15: Free-trial cost profile

**Status:** Accepted · **Date:** 2026-10-11 · **Revisit:** ~2026-11-11 (end of the Azure free trial)

## Context
The project is for learning and runs on a one-month Azure free account: a one-time credit for 30 days plus 12-month free services. Paid resources stop when the trial ends unless the subscription is upgraded. Free-trial subscriptions usually cannot purchase Azure Marketplace offers, and Claude on Foundry is billed through the Marketplace, so Claude may not be deployable.

## Options
| Option | Pros | Cons |
|---|---|---|
| **Free-trial profile** (cheapest tiers, one environment, no private endpoints, model fallback within Azure credits) | Stays within credits; architecture unchanged (only tiers and configuration) | Some production features (SLA, private networking) are documented rather than deployed |
| Production profile (v2 APIM tiers, private endpoints, separate demo environment) | Closest to production | Consumes the credit quickly |

## Decision
**Free-trial profile.**

| Area | Choice |
|---|---|
| Region | **East US 2** (single region; broad Foundry model availability). India data residency documented as the production consideration |
| Model | **Claude on Foundry if deployable on the trial; otherwise an Azure OpenAI chat model on Foundry** (within credits). Selected by configuration in the LLM gateway; prompts and evals rerun on switch |
| Embeddings | Azure OpenAI `text-embedding-3-small` on Foundry |
| APIM | **Consumption** if it supports the required AI-gateway policies; otherwise **Developer**. Verified at M1 setup |
| PostgreSQL | Flexible Server **B1ms** (12-month free allowance) |
| Container Apps | Consumption plan; idle services scale to zero, except during recording (min 1 replica) |
| Static Web Apps | Free tier |
| Content Safety | Free tier (F0) |
| Networking | Middle ground without private endpoints: internal ingress for MCP server and Order Platform, PostgreSQL firewall + Entra auth, Key Vault and Storage firewall + managed identity, ShopSense API accepts APIM only |
| Environments | One: `dev` (also used for demo; eval mode by configuration) |
| Budget | Alerts at 50% and 75% of the trial credit |

## Consequences
- Every choice is a tier or configuration value in the Bicep parameter file; moving to a production profile changes parameters, not architecture.
- If Claude is not available, deck and documentation state the substitution and the reason.
- Revisit around 2026-11-11: upgrade to pay-as-you-go or tear down (`azd down`).
