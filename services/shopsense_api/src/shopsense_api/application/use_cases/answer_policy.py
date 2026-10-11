"""Policy question answering: answers only from retrieved sections, with citations.

Checks, in order, all failing closed to a hand-off:
1. The model says it can answer and cites at least one section.
2. Every citation was retrieved (M3).
3. Every number in the answer occurs in the cited sections (numeric fabrication, M4 R4-6).
The blocked numbers are returned so the evaluation can count fabrication attempts."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from shopsense_api.application.ports.llm import LLMClient, StructuredRequest
from shopsense_api.application.ports.prompts import PromptRepository
from shopsense_api.application.untrusted_blocks import random_block_id, wrap_untrusted
from shopsense_api.application.use_cases.hybrid_search import HybridSearch, Mode
from shopsense_api.domain.policy.grounding import unsupported_numbers
from shopsense_api.domain.values.untrusted_text import UntrustedText

PROFILE = "policy"
PROMPT_NAME = "policy_answer"
HANDOFF = (
    "I could not find a clear answer in our policies, so I have passed your question "
    "to a support specialist."
)


class PolicyAnswerOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    can_answer: bool
    answer: str
    citations: list[str]


@dataclass(frozen=True, slots=True)
class PolicyAnswer:
    reply: str
    citations: tuple[str, ...]
    answered: bool
    blocked_numbers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnswerPolicyQuestion:
    llm: LLMClient
    prompts: PromptRepository
    search: HybridSearch

    async def run(
        self,
        question: UntrustedText,
        category: str | None = None,
        mode: Mode = "hybrid_rerank",
    ) -> PolicyAnswer:
        hits = await self.search.run(question.value, limit=4, category=category, mode=mode)
        if not hits:
            return PolicyAnswer(HANDOFF, (), answered=False)
        sections = "\n\n".join(
            f"[{h.chunk.chunk_id}] {h.chunk.title}\n{h.chunk.text}" for h in hits
        )
        block = wrap_untrusted("question", question, random_block_id())
        response = await self.llm.generate_structured(
            StructuredRequest(
                profile=PROFILE,
                system_prompt=self.prompts.get(PROMPT_NAME).text,
                user_message=f"{block}\n\nSections:\n{sections}",
                output_type=PolicyAnswerOut,
            )
        )
        texts = {h.chunk.chunk_id: h.chunk.text for h in hits}
        return _checked(response.output, texts)


def _checked(out: PolicyAnswerOut, retrieved: dict[str, str]) -> PolicyAnswer:
    cited = tuple(dict.fromkeys(out.citations))
    grounded = bool(cited) and set(cited) <= retrieved.keys()
    if not out.can_answer or not grounded:
        return PolicyAnswer(HANDOFF, (), answered=False)
    blocked = unsupported_numbers(out.answer, [retrieved[c] for c in cited])
    if blocked:
        return PolicyAnswer(HANDOFF, (), answered=False, blocked_numbers=tuple(sorted(blocked)))
    return PolicyAnswer(out.answer, cited, answered=True)
