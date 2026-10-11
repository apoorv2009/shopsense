"""Policy question answering (M3): answers only from retrieved sections, with citations.

Citations must be a subset of the retrieved chunk IDs. Anything else fails closed to a
hand-off, so a reply can never cite a section the model did not read."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from shopsense_api.application.ports.llm import LLMClient, StructuredRequest
from shopsense_api.application.ports.prompts import PromptRepository
from shopsense_api.application.untrusted_blocks import random_block_id, wrap_untrusted
from shopsense_api.application.use_cases.search_policy import SearchPolicy
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


@dataclass(frozen=True, slots=True)
class AnswerPolicyQuestion:
    llm: LLMClient
    prompts: PromptRepository
    search: SearchPolicy

    async def run(self, question: UntrustedText, category: str | None = None) -> PolicyAnswer:
        hits = await self.search.run(question.value, limit=4, category=category)
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
        return _checked(response.output, {h.chunk.chunk_id for h in hits})


def _checked(out: PolicyAnswerOut, retrieved: set[str]) -> PolicyAnswer:
    cited = tuple(dict.fromkeys(out.citations))
    grounded = bool(cited) and set(cited) <= retrieved
    if not out.can_answer or not grounded:
        return PolicyAnswer(HANDOFF, (), answered=False)
    return PolicyAnswer(out.answer, cited, answered=True)
