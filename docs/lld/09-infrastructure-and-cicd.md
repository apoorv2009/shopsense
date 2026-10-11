# LLD-9: Infrastructure as code and CI/CD

**Status:** Accepted · **Date:** 2026-10-11 · **Cost profile:** [D15 free trial](../adr/015-free-trial-profile.md)

## Table of contents
- [Decisions](#decisions)
- [Resources](#resources)
- [Identity and permissions](#identity-and-permissions)
- [Networking](#networking)
- [CI/CD](#cicd)
- [Naming and tags](#naming-and-tags)
- [Cost guardrails](#cost-guardrails)

## Decisions
| # | Decision |
|---|---|
| L9a | **Bicep + Azure Developer CLI (`azd`)**, using Azure Verified Modules where available |
| L9b | **East US 2**, except PostgreSQL in **Central US** (subscription region restriction, [D15](../adr/015-free-trial-profile.md)) |
| L9c | **APIM Consumption** if it supports the required AI-gateway policies; otherwise **Developer**; verified at M1 setup |
| L9d | **Middle-ground networking without private endpoints** |
| L9e | **One user-assigned managed identity per workload**; least privilege; PostgreSQL Entra auth; GitHub OIDC federation |
| L9f | **GitHub Actions**: PR checks per changed service + Bicep what-if; deploy on merge to main; LLM evals on demand |
| L9g | **One environment** (`dev`, also demo); eval mode by configuration |
| L9h | **Budget alerts** at 50% and 75% of trial credit; scale to zero when idle; min 1 replica while recording |
| L9i | **CAF naming and standard tags** |
| L9j | **Log Analytics + workspace-based Application Insights**; Langfuse Cloud (masked traces); Azure Workbook for D13 metrics |

## Resources
Resources are provisioned incrementally in the milestone that first needs them ([D16](../adr/016-milestone-alignment.md), [HLD §10](../01-hld.md#10-component-to-milestone-map)).

| Resource | Tier (free-trial profile) |
|---|---|
| Resource group | `rg-shopsense-dev-eus2` |
| API Management | Consumption (fallback Developer) |
| Container Apps environment + apps: `shopsense-api`, `shopsense-worker`, `mcp-server`, `order-platform`, `qdrant` | Consumption |
| Container Registry | Basic |
| PostgreSQL Flexible Server (DBs `shopsense`, `order_platform`) | B1ms |
| Storage account (Azure Files for Qdrant, Blob for evidence, queue for replies) | Standard LRS |
| Key Vault (secrets, signing key) | Standard |
| AI Foundry project (chat model, embeddings, evaluators; reranker if available) | Pay-per-token within credits |
| Content Safety | F0 |
| Logic Apps (inbound email, outbound replies) | Consumption |
| Static Web Apps (Angular) | Free |
| Log Analytics + Application Insights | Pay-per-GB (free allowance) |
| Entra ID app registrations (SPA, API, MCP, Order Platform), test users, roles | Free |

## Identity and permissions
| Identity | Permissions |
|---|---|
| `id-shopsense-api` | Key Vault key **sign**; `shopsense` DB; Blob (evidence) read/write; queue send; Foundry; Content Safety; Microsoft Graph user read |
| `id-shopsense-worker` | `shopsense` DB; key **sign** (grants for outbox); queue send |
| `id-mcp-server` | Key **verify**; call Order Platform |
| `id-order-platform` | Key **verify**; `order_platform` DB |
| `id-logic-inbound`, `id-logic-outbound` | Call APIM `/email`; queue receive; mailbox connector |
| GitHub Actions (OIDC) | Deploy to the resource group; push to ACR |

## Networking
- Container Apps environment with internal ingress for `mcp-server`, `order-platform` and `qdrant`.
- `shopsense-api` external ingress restricted to APIM (IP allow-list + APIM-injected header validated by the API).
- PostgreSQL: public access restricted by firewall to the Container Apps environment; Entra authentication only.
- Key Vault and Storage: firewall + managed identity.
- Production profile (documented, not deployed): VNet-integrated APIM, private endpoints, private DNS.

## CI/CD
| Workflow | Trigger | Steps |
|---|---|---|
| `ci.yml` | Pull request | Per changed service: `ruff check`, `ruff format --check`, `mypy --strict`, `pytest --cov`; frontend: ESLint, Prettier, Vitest, build; Bicep what-if comment |
| `deploy.yml` | Merge to main | Build images → push to ACR → `azd deploy` |
| `eval.yml` | Manual | Golden + red-team sets ×3 against `dev`; publish report |

## Naming and tags
- Names follow the Cloud Adoption Framework: `rg-`, `apim-`, `cae-`, `ca-`, `psql-`, `kv-`, `st-`, `log-`, `appi-`, `swa-`, `logic-` prefixes with `shopsense-dev-eus2`.
- Tags: `project=shopsense`, `env=dev`, `owner=apoorv2009`, `purpose=learning`.

## Cost guardrails
- Budget alerts at 50% and 75% of the trial credit.
- Scale to zero when idle; min 1 replica during recording.
- Stop PostgreSQL when not in use.
- Tear down with `azd down` if not upgrading at the revisit date.
