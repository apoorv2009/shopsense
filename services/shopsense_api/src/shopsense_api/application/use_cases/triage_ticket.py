"""Triage use case (M1): untrusted ticket text -> validated SupportTicket.

One retry on invalid output, with the validation problems fed back; a second failure
raises TriageFailed so the ticket fails closed to a human (L5c).
"""

from dataclasses import dataclass, field

from shopsense_api.application.ports.llm import (
    LLMClient,
    StructuredRequest,
    StructuredResponse,
    TokenUsage,
)
from shopsense_api.application.ports.prompts import PromptRepository
from shopsense_api.application.untrusted_blocks import (
    BlockIdFactory,
    random_block_id,
    wrap_untrusted,
)
from shopsense_api.domain.exceptions import LLMOutputInvalid, TriageFailed
from shopsense_api.domain.guardrails.injection_screen import looks_like_injection
from shopsense_api.domain.ticket.enums import RiskFlag
from shopsense_api.domain.ticket.support_ticket import SupportTicket
from shopsense_api.domain.values.untrusted_text import UntrustedText

PROFILE = "triage"
PROMPT_NAME = "triage"
MAX_ATTEMPTS = 2


@dataclass(frozen=True, slots=True)
class TriageCommand:
    message: UntrustedText
    recent_turns: tuple[UntrustedText, ...] = ()


@dataclass(frozen=True, slots=True)
class TriageResult:
    ticket: SupportTicket
    provider: str
    model: str
    prompt_version: str
    attempts: int
    usage: TokenUsage
    regex_injection_hit: bool = field(default=False)


class TriageTicket:
    def __init__(
        self,
        llm: LLMClient,
        prompts: PromptRepository,
        block_ids: BlockIdFactory = random_block_id,
    ) -> None:
        self._llm = llm
        self._prompts = prompts
        self._block_ids = block_ids

    async def execute(self, command: TriageCommand) -> TriageResult:
        prompt = self._prompts.get(PROMPT_NAME)
        base_message = self._user_message(command)
        feedback: tuple[str, ...] = ()
        for attempt in range(1, MAX_ATTEMPTS + 1):
            request = StructuredRequest(
                profile=PROFILE,
                system_prompt=prompt.text,
                user_message=_with_feedback(base_message, feedback),
                output_type=SupportTicket,
            )
            try:
                response = await self._llm.generate_structured(request)
            except LLMOutputInvalid as exc:
                feedback = exc.problems
                continue
            return _finish(command, response, prompt.version, attempt)
        raise TriageFailed(f"triage output invalid after {MAX_ATTEMPTS} attempts")

    def _user_message(self, command: TriageCommand) -> str:
        block_id = self._block_ids()
        parts = [
            wrap_untrusted("previous_message", turn, block_id) for turn in command.recent_turns
        ]
        parts.append(wrap_untrusted("ticket", command.message, block_id))
        return "\n\n".join(parts)


def _finish(
    command: TriageCommand,
    response: StructuredResponse[SupportTicket],
    prompt_version: str,
    attempts: int,
) -> TriageResult:
    ticket = response.output
    regex_hit = looks_like_injection(command.message.value)
    if regex_hit:
        ticket = ticket.with_flag(RiskFlag.PROMPT_INJECTION_SUSPECTED)
    return TriageResult(
        ticket=ticket,
        provider=response.provider,
        model=response.model,
        prompt_version=prompt_version,
        attempts=attempts,
        usage=response.usage,
        regex_injection_hit=regex_hit,
    )


def _with_feedback(message: str, problems: tuple[str, ...]) -> str:
    if not problems:
        return message
    listed = "\n".join(f"- {p}" for p in problems)
    return (
        f"{message}\n\nYour previous answer failed validation:\n{listed}\n"
        "Return a corrected answer."
    )
