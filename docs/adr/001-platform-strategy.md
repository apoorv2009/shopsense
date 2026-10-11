# D1: Platform strategy — course stack plus Azure AI Foundry

**Status:** Accepted · **Date:** 2026-10-10

## Context
The milestones name specific technology (Pydantic, Qdrant, LangGraph, MCP, Langfuse, FastAPI). Azure AI Foundry offers managed equivalents for several of these, and an Azure subscription is available. The project also serves as portfolio material where an Azure story has value.

## Options
**A. Fully Foundry-native** (Agent Service, AI Search, App Insights, Foundry evaluations)
- Pros: one managed platform; built-in evaluators and Prompt Shields; strong enterprise story.
- Cons: replaces three course-named tools (Qdrant, LangGraph, Langfuse), risking milestone marks; Agent Service hides the orchestration the course wants built; largest learning curve.

**B. Hybrid**: course stack, plus Foundry where it adds value without replacing a named tool
- Pros: every milestone shows the expected technology; real Azure usage; Foundry stays swappable.
- Cons: needs an Azure subscription; more moving parts than C.

**C. Course stack only**, direct Anthropic API
- Pros: fastest and cheapest; exact milestone match.
- Cons: no Azure story.

## Decision
**Option B.** Foundry provides the model endpoint (Claude via `AnthropicFoundry`), groundedness evaluation (`azure-ai-evaluation`) and Prompt Shields (Azure AI Content Safety). Each sits behind our own interface (LLM client, evaluator, safety checker).

## Consequences
- Azure packages limited to `anthropic` (Foundry client), `azure-identity`, `azure-ai-evaluation`, `azure-ai-contentsafety`.
- Provider fallback to the direct Anthropic API or an Azure OpenAI model is a configuration change.
- Exact package versions and preview status to be verified at setup time.
