# M1 — Ticket parsing

> **Brief:** Parse support tickets into a validated Pydantic `SupportTicket` object (issue type, order ID, sentiment, urgency) via a provider-agnostic client.

## Table of contents
- [What was built](#what-was-built)
- [How it maps to the brief](#how-it-maps-to-the-brief)
- [Setup](#setup)
- [Run](#run)
- [Results](#results)

## What was built
| Piece | Location |
|---|---|
| `SupportTicket` (frozen Pydantic model) | `services/shopsense_api/src/shopsense_api/domain/ticket/support_ticket.py` |
| Value objects: `UntrustedText`, `OrderId`, `Money` (paise) | `.../domain/values/` |
| Deterministic injection screen | `.../domain/guardrails/injection_screen.py` |
| `LLMClient` port (profile-based, provider-free) | `.../application/ports/llm.py` |
| `TriageTicket` use case (random-ID delimiters, one retry, fail closed) | `.../application/use_cases/triage_ticket.py` |
| Triage prompt v1 | `.../application/prompts/triage/v1.md` |
| LLM gateway (routing, fallback, token metering) | `.../adapters/llm/gateway.py` |
| Providers: OpenAI `gpt-4.1-mini` and Mistral AI `mistral-medium-2505` on Foundry (OpenAI-compatible adapter); Claude adapter (disabled on the free trial) | `.../adapters/llm/foundry_openai.py`, `anthropic_foundry.py` |
| Golden set (20) + Bitext-based suite generator | `evals/` |
| Infrastructure (Foundry, both model deployments) | `infra/m1/` |

## How it maps to the brief
| Brief | Implementation |
|---|---|
| Parse support tickets | `TriageTicket` use case; untrusted text wrapped in per-request random-ID tags |
| Validated Pydantic `SupportTicket` | Frozen model, `extra="forbid"`; order ID format, amount ≥ 0, summary length enforced; invalid output retried once then fails closed |
| Issue type, order ID, sentiment, urgency | Required fields (plus category hint, amount in paise, risk flags, language, summary) |
| Provider-agnostic client | Use case depends only on the `LLMClient` port; the gateway routes the `triage` profile to OpenAI, Mistral AI or Claude by configuration, with fallback between vendors |

## Setup
1. Install the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) and sign in: `az login`.
2. Deploy M1 infrastructure (gpt-4.1-mini + mistral-medium-2505; add `deployClaude=true claudeOrganizationName=...` only with Claude quota):
   ```bash
   az deployment sub create --location eastus2 --template-file infra/m1/main.bicep --parameters principalId=$(az ad signed-in-user show --query id -o tsv)
   ```
3. Copy `.env.example` to `.env` and fill in the deployment outputs.
4. Install: `uv sync --all-packages`.

## Run
```bash
uv run pytest                                   # offline unit tests
uv run pytest -m integration                    # live check of both providers (costs tokens)
uv run python milestones/m1/demo.py --eval      # demo + golden set
uv run shopsense-eval generate-suite --n 150    # one-time: noisy Bitext-based suite
uv run shopsense-eval triage --suite all --runs 3
```

## Results
*To be filled in after the first live run (accuracy per field, flag recall, gate status for each of 3 runs).*
