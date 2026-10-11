"""Escalation Reviewer agent (M6): writes a brief for the human specialist about a held case.

It has no tools and writes nothing. Its brief is shown to the reviewer; the decision stays with a
person (approval interrupt), so the brief can inform but never execute."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from shopsense_api.application.ports.llm import LLMClient, StructuredRequest
from shopsense_api.application.ports.prompts import PromptRepository
from shopsense_api.application.untrusted_blocks import random_block_id, wrap_untrusted
from shopsense_api.domain.values.untrusted_text import UntrustedText

PROFILE = "review"
PROMPT_NAME = "reviewer"


class ReviewBriefOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    summary: str = Field(min_length=1, max_length=600)
    risk_notes: list[str]
    recommendation: Literal["approve", "reject", "more_info"]


@dataclass(frozen=True, slots=True)
class EscalationReviewer:
    llm: LLMClient
    prompts: PromptRepository

    async def run(self, message: UntrustedText, facts: dict[str, Any]) -> dict[str, Any]:
        block = wrap_untrusted("question", message, random_block_id())
        facts_text = "\n".join(f"- {key}: {value}" for key, value in sorted(facts.items()))
        response = await self.llm.generate_structured(
            StructuredRequest(
                profile=PROFILE,
                system_prompt=self.prompts.get(PROMPT_NAME).text,
                user_message=f"{block}\n\nSystem facts:\n{facts_text}",
                output_type=ReviewBriefOut,
            )
        )
        out = response.output
        return {
            "summary": out.summary,
            "risk_notes": list(out.risk_notes),
            "recommendation": out.recommendation,
        }
