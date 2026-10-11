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
| Providers: OpenAI `gpt-4.1-mini` and Meta `Llama-3.3-70B-Instruct` on Foundry (OpenAI-compatible adapter; JSON mode for Llama); Claude adapter (disabled on the free trial) | `.../adapters/llm/foundry_openai.py`, `anthropic_foundry.py` |
| Golden set (20) + Bitext-based suite generator | `evals/` |
| Infrastructure (Foundry, both model deployments) | `infra/m1/` |

## How it maps to the brief
| Brief | Implementation |
|---|---|
| Parse support tickets | `TriageTicket` use case; untrusted text wrapped in per-request random-ID tags |
| Validated Pydantic `SupportTicket` | Frozen model, `extra="forbid"`; order ID format, amount ≥ 0, summary length enforced; invalid output retried once then fails closed |
| Issue type, order ID, sentiment, urgency | Required fields (plus category hint, amount in paise, risk flags, language, summary) |
| Provider-agnostic client | Use case depends only on the `LLMClient` port; the gateway routes the `triage` profile to OpenAI, Meta Llama or Claude by configuration, with fallback between vendors |

## Setup
1. Install the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) and sign in: `az login`.
2. Deploy M1 infrastructure (gpt-4.1-mini + Llama-3.3-70B-Instruct; add `deployClaude=true claudeOrganizationName=...` only with Claude quota):
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
Live runs on 2026-10-11, Azure AI Foundry (East US 2), prompt `triage/v2`.

### Full suite: 170 tickets (20 golden + 150 generated from Bitext), `gpt-4.1-mini`, 3 runs
| Field | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| issue_type | 88% | 89% | 91% |
| order_id | 100% | 100% | 100% |
| sentiment | 88% | 89% | 87% |
| urgency | 95% | 97% | 96% |
| flags | 100% | 100% | 100% |
| language | 99% | 99% | 99% |
| **mean field accuracy** (target ≥ 85%) | **95%** | **96%** | **96%** |
| all fields correct | 78% | 80% | 79% |

| Zero-tolerance gate | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Prompt-injection recall | 13/13 | 13/13 | 13/13 |
| Legal-threat recall | 8/8 | 8/8 | 8/8 |
| Product-safety recall | 7/7 | 7/7 | 7/7 |
| Errors | 0 | 0 | 0 |
| Gates | PASS | PASS | PASS |

Safety-screen false positives: 0 in every run.

### Provider-agnostic client: golden set (20 tickets), one run per vendor
| Vendor · model | Mean field accuracy | All fields correct | Gates |
|---|---|---|---|
| OpenAI · `gpt-4.1-mini` (schema-constrained output) | 100% | 100% | PASS |
| Meta · `Llama-3.3-70B-Instruct` (JSON mode + Pydantic validation) | 98% | 90% | PASS |

### What the live runs taught us
| Finding | Fix |
|---|---|
| Async Entra auth needs `aiohttp` | Dependency added |
| Rate limits at 10k TPM made the gateway fall back to Llama mid-run | Capacity raised; SDK retries honour `Retry-After` |
| "SYSTEM: refund approved" injections slipped past model and screen | Fake role-marker patterns in the screen; prompt v2 example |
| Azure content filter returns HTTP 400 for some injections | Mapped to `LLMRefused` (fails closed to a human); counted as caught |
| Model set issue type `product_safety` but omitted the flag once | Domain invariant (issue type implies flag) + deterministic safety screen |
| Generated "neutral" tickets contained social-media threats | Spec bug fixed (threat ⇒ at least frustrated); generator prompt calibrates anger |

### Known limitations
- Sentiment and issue type on generated tickets carry some label noise (synthetic anger is weaker than real anger; delivery problems overlap with replacement requests). Golden-set labels are hand-curated.
- Claude adapter is implemented and unit-tested but disabled: the free-trial subscription has zero Claude quota ([D15](../../docs/adr/015-free-trial-profile.md)).

