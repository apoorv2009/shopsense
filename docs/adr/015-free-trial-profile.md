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
| Model | **Primary: OpenAI `gpt-4.1-mini`; second vendor: Meta `Llama-3.3-70B-Instruct`** (JSON mode + Pydantic validation), both sold directly by Azure on the same Foundry resource and within trial credits. **Amended 2026-10-11:** the trial subscription has zero quota for every Claude model, and Marketplace-billed models (Claude, Mistral Medium) cannot be purchased on a free subscription; the project has no requirement to use Claude. The Claude adapter stays in the code, enabled by configuration where quota exists |
| Embeddings | Azure OpenAI `text-embedding-3-small` on Foundry |
| APIM | **Consumption** if it supports the required AI-gateway policies; otherwise **Developer**. Verified at M1 setup |
| PostgreSQL | Flexible Server **B1ms** (12-month free allowance), in **Central US**: the trial subscription is restricted from provisioning PostgreSQL in East US 2, East US, West US 2 and South India (checked 2026-10-11). Central US keeps the database in the same geography as the Foundry models for low latency once services run in Azure (M8) |
| Container Apps | Consumption plan; idle services scale to zero, except during recording (min 1 replica) |
| Static Web Apps | Free tier |
| Content Safety | Free tier (F0) |
| Networking | Middle ground without private endpoints: internal ingress for MCP server and Order Platform, PostgreSQL firewall + Entra auth, Key Vault and Storage firewall + managed identity, ShopSense API accepts APIM only |
| Environments | One: `dev` (also used for demo; eval mode by configuration) |
| Budget | Alerts at 50% and 75% of the trial credit |

## Quota check (2026-10-11, East US 2)
| Model | Quota (k TPM) |
|---|---|
| All Claude models | 0 |
| gpt-4.1-mini (GlobalStandard) | 200 |
| mistral-medium-2505 | 20 (but Marketplace: not purchasable on a free subscription) |
| Llama-3.3-70B-Instruct | 20 |
| text-embedding-3-small (GlobalStandard) | 1,000 |
| Cohere Rerank v4 (Fast / Pro) | 20 |

## Consequences
- Every choice is a tier or configuration value in the Bicep parameter file; moving to a production profile changes parameters, not architecture.
- Revisit around 2026-11-11: upgrade to pay-as-you-go or tear down (`azd down`).
