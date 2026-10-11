# LLD-5: Agent designs

**Status:** Accepted · **Date:** 2026-10-11 · **Milestones:** M1 (Triage), M2 (Order-Actions), M3–M4 (Policy RAG), M5–M6 (Reviewer, Composer)

## Table of contents
- [Decisions](#decisions)
- [Model configuration](#model-configuration)
- [Prompt structure](#prompt-structure)
- [Agent specifications](#agent-specifications)
- [Composer placeholders](#composer-placeholders)
- [Reviewer-facing safety](#reviewer-facing-safety)

## Decisions
| # | Decision |
|---|---|
| L5a | **Model per agent is configuration in the LLM gateway.** Free-trial baseline ([D15](../adr/015-free-trial-profile.md)): OpenAI `gpt-4.1-mini` for every agent, Meta `Llama-3.3-70B-Instruct` as second vendor and fallback (JSON mode). The original Claude Opus 5.5 plan (effort per agent) applies where Claude quota exists; `effort` is ignored by models that do not support it |
| L5b | **Structured outputs for every agent**, validated by Pydantic at the adapter edge and mapped to domain dataclasses; no free-text parsing |
| L5c | **Limits per run**: Order-Actions ≤ 6 tool calls and 20 s; token budget per agent; one retry on validation failure; any breach fails closed to the human queue |
| L5d | **Stable, cacheable system prompts**; untrusted text only in the user message inside delimiter tags with a **per-request random ID**; prompts versioned in the repo and recorded in traces |
| L5e | **Composer uses placeholders** for every critical fact, filled by code from trusted state; output guard rejects digits or ₹ amounts outside filled placeholders |
| L5f | **Reviewer console separates** code-generated risk reasons (trusted), the AI summary (labelled), and the customer's raw words (marked panel); decisions act only on the code-computed proposed action |

## Model configuration
Effort levels below apply to models that support effort (Claude); OpenAI and Llama models use their defaults.

| Agent | Effort (baseline) | Rationale |
|---|---|---|
| Triage | Low | Classification and extraction |
| Policy RAG | Medium | Explanation from retrieved text |
| Order-Actions | Medium | Short tool loop |
| Escalation Reviewer | High | Judgement on risky cases |
| Composer | Low | Wording only; facts come from code |

## Prompt structure
| Part | Contents | Trust |
|---|---|---|
| System prompt | Role, rules, output contract, few-shot examples (Bitext-derived) | Ours; stable; cached |
| User message | Trusted facts block (from state) + untrusted text inside `<ticket id="{random}">…</ticket>` | Mixed, clearly delimited |
| Output | Schema-constrained JSON | Validated at the edge |

## Agent specifications
| | Triage | Policy RAG | Order-Actions | Escalation Reviewer | Composer (LLM step) |
|---|---|---|---|---|---|
| Job | Ticket text → `SupportTicket` | Explain and cite the rules-engine decision; answer questions rules do not cover | Investigate the order; propose one action | Case summary and recommendation for a human | Customer reply wording |
| Reads | Current message, last 3 turns, memory summary | `ticket`, rules result, retrieved chunks | `ticket`, `policy_findings`, read tools | Whole state + memory | Decision, tool facts, citations, language |
| Tools | None | `search_policy` | MCP read tools (5) | None | None |
| Writes | `ticket` | `policy_findings` (explanation, citations) | `proposed_action` | `review` | `reply` (template with placeholders) |
| Cannot | Route; call tools | Change the rules result | Execute writes; choose the amount (from `calculate_refund`) | Approve or reject | Write raw numbers |
| On failure | Retry once → human | Retrieval error → human | Typed tool error → human | Code-built plain-facts summary | Guard fails twice → holding reply |
| Evaluated by | Triage suite | Retrieval + groundedness | Tool-use suite | Golden set + human spot-check | Fabrication check + tone sample |

## Composer placeholders
| Placeholder | Filled from |
|---|---|
| `{refund_amount}` | `proposed_action` / `execution` (`Money`) |
| `{return_window_days}`, `{days_since_delivery}` | Rules-engine result |
| `{refund_eta}` | Refund timelines rule (payment method) |
| `{order_no}`, `{ticket_no}` | State |
| `{carrier}`, `{awb}`, `{promised_date}` | Tracking tool result |
| `{approval_turnaround}` | Approver tier (authorisation matrix) |

Unknown placeholders or digits outside placeholders fail the output guard.

## Reviewer-facing safety
- Risk reasons shown come from the risk gate (code), never from the model.
- The AI summary is labelled "AI-generated" and cannot change the action under review.
- Customer text appears only in a marked "customer's own words" panel.
- Approve / reject apply to the code-computed `proposed_action` only.
