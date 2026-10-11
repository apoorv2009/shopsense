"""Groundedness judge (M4 R4-7): an LLM grades an answer against the sections it cites.

The judge is a measurement tool for the evaluation, not a gate in the customer path. Its
verdicts are reported (mean score, share supported) so the claim 'the assistant never invents
a window or amount' has a number behind it."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from shopsense_api.application.ports.llm import LLMClient, StructuredRequest
from shopsense_api.application.ports.prompts import PromptRepository
from shopsense_api.application.untrusted_blocks import random_block_id, wrap_untrusted
from shopsense_api.domain.values.untrusted_text import UntrustedText

PROFILE = "policy"
PROMPT_NAME = "judge"


class JudgeOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    score: int = Field(ge=1, le=5)
    supported: bool
    unsupported_claims: list[str]


@dataclass(frozen=True, slots=True)
class Verdict:
    score: int
    supported: bool
    unsupported_claims: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GroundednessJudge:
    llm: LLMClient
    prompts: PromptRepository

    async def run(self, question: UntrustedText, answer: str, sources: list[str]) -> Verdict:
        body = "\n\n".join(sources)
        user = (
            f"{wrap_untrusted('question', question, random_block_id())}\n\n"
            f"Answer:\n{answer}\n\nSections:\n{body}"
        )
        response = await self.llm.generate_structured(
            StructuredRequest(PROFILE, self.prompts.get(PROMPT_NAME).text, user, JudgeOut)
        )
        out = response.output
        return Verdict(out.score, out.supported, tuple(out.unsupported_claims))
