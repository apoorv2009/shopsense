# LLD-6: Rules engine, policy rules-block format and retrieval

**Status:** Accepted · **Date:** 2026-10-11 · **Milestones:** M3 (ingestion, rules), M4 (hybrid search, rerank, consistency), M6/M8 (photo evidence)

## Table of contents
- [Decisions](#decisions)
- [Rules-block format](#rules-block-format)
- [Fact provenance](#fact-provenance)
- [Photo evidence](#photo-evidence)
- [Precedence](#precedence)
- [Date arithmetic](#date-arithmetic)
- [Retrieval](#retrieval)
- [Consistency check](#consistency-check)

## Decisions
| # | Decision |
|---|---|
| L6a | **Rules block inside each section**, directly after the clause it encodes |
| L6b | **Fact provenance**: facts labelled *system* or *customer-asserted*; rules may use asserted facts as **recorded assumptions**, stated in the reply; fraud signals in the risk gate |
| L6b-2 | **Photo evidence checked by Claude vision**; auto-resolution under the cap only when the check is confident; otherwise human review |
| L6c | **Most specific rule wins**: explicit overrides → specificity → tie is a policy error; ambiguity detected at load time |
| L6d | **Calendar days in IST from delivery, inclusive**; injected `Clock`; exhaustive boundary tests |
| L6e | **Decision citations by direct section lookup**; **open questions by hybrid search** (dense + sparse, RRF top 20 → rerank top 4, category filter + general docs) |
| L6f | **Reranker behind a `Reranker` port**: Cohere Rerank via Foundry if available; local ONNX cross-encoder (fastembed) as automatic fallback |
| L6g | **Consistency check**: values validated against section text at load; section content hash checked at citation time; mismatch → escalate |

## Rules-block format
Each rule appears in the section whose clause it encodes.

| Field | Meaning |
|---|---|
| `rule_id` | Stable ID, e.g. `ELE-RET-15` |
| `kind` | return_window · not_returnable · exception · warranty · refund_method · refund_timeline |
| `applies_to` | category, is_accessory, item_condition, price_below_paise, reported_within_hours |
| `window_days` | Integer, counted per [date arithmetic](#date-arithmetic) |
| `outcome` | return (refund or replacement) · replacement_only · repair_or_replace · not_returnable · escalate |
| `overrides` | Rule IDs this rule replaces |
| `requires_evidence` | none · photo |
| `citation` | doc_id + section (implicit from location) |

Example (electronics addendum §1): rule `ELE-RET-15` — category electronics, not accessory · 15 days from delivery · outcome return · overrides `RET-GEN-30`.

## Fact provenance
| Provenance | Examples | Use |
|---|---|---|
| System | Delivery date, category, accessory flag, price paid, payment method | Decisions |
| Customer-asserted | Defective, unopened, damaged on arrival, wrong item | Recorded assumptions; listed in the decision and stated in the reply |
| Verified evidence | Photo check result (confident match) | Satisfies `requires_evidence: photo` |

## Photo evidence
Applies when a matched rule has `requires_evidence: photo` (damaged, wrong or missing items within 48 hours).

| Step | Design |
|---|---|
| Upload | Chat: attachment upload to the ticket; email: attachments forwarded by the Logic App. JPEG/PNG only, ≤ 5 MB, ≤ 3 per turn |
| Storage | Azure Blob Storage (private container, per-ticket path); image re-encoded on upload to strip metadata and neutralise malformed files |
| Check | **Evidence checker (LLM vision step)**: given the claim and order item, returns `matches_claim` (yes / no / uncertain), confidence, observations |
| Image text | Any text inside an image is untrusted; the checker prompt treats embedded instructions as data |
| Outcome | Confident "yes" + amount within cap → evidence satisfied; "no" or "uncertain" or low confidence → human review via the risk gate |
| Retention | Same as ticket raw text (90 days after closure) |

Resulting design additions: state section `evidence` ([LLD-1](01-ticket-state.md)), ports `EvidenceStore` and use case *check evidence* ([LLD-2](02-shopsense-api-structure.md)), table `attachments` ([LLD-3](03-data-models.md)), endpoint `POST /v1/tickets/{id}/attachments`, and Azure Blob Storage.

## Precedence
1. Explicit `overrides`.
2. Specificity: more matching conditions beat fewer (accessory rule > electronics rule > general rule).
3. Remaining tie → policy error. Detected when rules are loaded; loading fails with the conflicting rule IDs.

## Date arithmetic
- Days = calendar days in Asia/Kolkata between delivery date and today; "within N days" is inclusive of day N.
- 48-hour windows use timestamps, not calendar days.
- Boundary tests: day 0, day N, day N+1, accessory 7/8, 48 h ± 1 minute.

## Retrieval
| Path | Used for | Method |
|---|---|---|
| Direct lookup | Citations for rules-engine decisions | Fetch the rule's section by doc_id + section |
| Hybrid search | Open questions not covered by rules | Dense + sparse, Qdrant RRF fusion (top 20), payload filter (product category + general), rerank to top 4 |

## Consistency check
| When | Check | On failure |
|---|---|---|
| Load time | Rule values (window, outcome) appear in their section's text; no unresolved precedence ties | Loading fails |
| Citation time | Retrieved section content hash equals the rule's stored source hash | Mismatch → escalate |
