# D9: Conversation model and long-term memory

**Status:** Accepted · **Date:** 2026-10-11

## Context
Short-term memory (what has been said in this ticket) lives in LangGraph state and checkpoints. Long-term memory (what we know about the customer across tickets) is M3's per-customer memory. Ticket text is attacker-controlled.

## D9a: Conversation-to-workflow mapping
| Option | Assessment |
|---|---|
| **One ticket = one LangGraph thread** | Context per issue; approval pauses are paused threads; reliable contact counting |
| One thread per customer | Unbounded context; unrelated issues mixed |
| One thread per message | Loses multi-turn conversation |

**Decision:** ticket ID = thread ID. New messages resume the thread. A message about the same order within 7 days of closure **reopens** the ticket; otherwise a new ticket is created.

## D9b: Long-term memory content
| Option | Pros | Cons |
|---|---|---|
| **Structured facts in Postgres** | Exact; readable by the risk gate; cheap | No fuzzy recall |
| Structured + semantic recall (Qdrant) | Richer context | More work; little value at demo scale |
| LLM-written free-text notes | Flexible | Memory-poisoning risk |

**Decision:** structured facts in Postgres, designed so semantic recall can be added later.
- Ticket history: issue type, order, outcome, sentiment, resolution date, one-line neutral summary
- Preferences: language, refund method, channel, from fixed allowed values only
- Risk counters: contacts per order in the last 7 days, automatic refunds in the last 30 days

## Anti-poisoning rule
Long-term memory stores **only system-derived facts** (validated triage fields, tool results, outcomes) and **never raw customer text**. Prevents an attacker planting instructions ("this customer is pre-approved for refunds") that would be replayed into future prompts.

## Consequences
- The 30-day automatic-refund counter enforces the refund authorisation policy.
- The 7-day contact counter drives the "third contact" escalation rule.
