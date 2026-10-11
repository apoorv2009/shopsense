"""Order-Actions agent (M2): a single tool-calling agent over the order system.

Loop: the model calls order tools until it submits an OrderActionsResult through the
`submit_result` tool. Limits (L5c) fail closed: when exceeded, code builds a
"needs a human" result instead of trusting a partial answer.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from shopsense_api.application.agents.order_tools_registry import TOOLS, ToolExecutor
from shopsense_api.application.ports.llm import TokenUsage
from shopsense_api.application.ports.orders import OrderTools
from shopsense_api.application.ports.prompts import PromptRepository
from shopsense_api.application.ports.tool_llm import (
    ChatMessage,
    ToolCall,
    ToolCallingLLM,
    ToolSpec,
    ToolTurnRequest,
)
from shopsense_api.application.untrusted_blocks import (
    BlockIdFactory,
    random_block_id,
    wrap_untrusted,
)
from shopsense_api.domain.guardrails.injection_screen import looks_like_injection
from shopsense_api.domain.values.untrusted_text import UntrustedText

PROFILE = "order_actions"
ORDER_NO = re.compile(r"\bORD-\d{6}\b", re.IGNORECASE)
PROMPT_NAME = "order_actions"
SUBMIT = "submit_result"


class Outcome(StrEnum):
    RESOLVED = "resolved"
    PENDING_HUMAN_APPROVAL = "pending_human_approval"
    NEEDS_CUSTOMER_INFO = "needs_customer_info"
    CANNOT_HELP = "cannot_help"


class ActionTaken(BaseModel):
    tool: str
    order_no: str | None = None
    detail: str = Field(max_length=200)


class OrderActionsResult(BaseModel):
    outcome: Outcome
    actions: list[ActionTaken] = Field(
        description="Write actions taken (refunds, replacements); empty if none."
    )
    customer_reply: str = Field(
        max_length=1200, description="Reply to the customer, based only on tool results."
    )
    needs_human: bool
    reason: str = Field(max_length=300, description="Why this outcome, in one sentence.")


@dataclass(frozen=True, slots=True)
class AgentLimits:
    max_tool_calls: int = 6
    max_turns: int = 8
    timeout_s: float = 60.0


DEFAULT_LIMITS = AgentLimits()
HANDOFF_REPLY = (
    "Thanks for your patience. A support specialist will review your request "
    "and get back to you shortly."
)


@dataclass(frozen=True, slots=True)
class OrderActionsCommand:
    customer_id: str  # verified identity (trusted), never from the model
    run_id: str
    message: UntrustedText


@dataclass(slots=True)
class OrderActionsRun:
    result: OrderActionsResult
    tool_log: list[dict[str, Any]]
    turns: int = 0
    usage: TokenUsage = field(default_factory=lambda: TokenUsage(0, 0))
    limit_hit: str | None = None


class OrderActionsAgent:
    def __init__(
        self,
        llm: ToolCallingLLM,
        prompts: PromptRepository,
        tools: OrderTools,
        limits: AgentLimits = DEFAULT_LIMITS,
        block_ids: BlockIdFactory = random_block_id,
    ) -> None:
        self._llm, self._prompts, self._tools = llm, prompts, tools
        self._limits, self._block_ids = limits, block_ids

    async def run(self, command: OrderActionsCommand) -> OrderActionsRun:
        # Deterministic guard: a ticket that tries to instruct the system never triggers a write
        writes_allowed = not looks_like_injection(command.message.value)
        named = frozenset(m.upper() for m in ORDER_NO.findall(command.message.value))
        executor = ToolExecutor(
            self._tools,
            command.customer_id,
            command.run_id,
            writes_allowed=writes_allowed,
            named_orders=named,
        )
        run = OrderActionsRun(_fallback("not started"), executor.log)
        try:
            async with asyncio.timeout(self._limits.timeout_s):
                await self._loop(command, executor, run)
        except TimeoutError:
            run.limit_hit = "timeout"
            run.result = _fallback("time limit reached")
        run.result = _consistent(run.result, executor.log)
        return run

    async def _loop(
        self, command: OrderActionsCommand, executor: ToolExecutor, run: OrderActionsRun
    ) -> None:
        prompt = self._prompts.get(PROMPT_NAME)
        messages = [
            ChatMessage("user", wrap_untrusted("ticket", command.message, self._block_ids()))
        ]
        tool_calls = 0
        for run.turns in range(1, self._limits.max_turns + 1):
            request = ToolTurnRequest(PROFILE, prompt.text, tuple(messages), _specs())
            turn = await self._llm.complete_with_tools(request)
            run.usage = TokenUsage(
                run.usage.input_tokens + turn.usage.input_tokens,
                run.usage.output_tokens + turn.usage.output_tokens,
            )
            messages.append(ChatMessage("assistant", turn.content, turn.tool_calls))
            if not turn.tool_calls:
                messages.append(ChatMessage("user", f"Finish by calling {SUBMIT}."))
                continue
            for call in turn.tool_calls:
                if call.name == SUBMIT and (result := _parse_result(call)) is not None:
                    run.result = result
                    return
                tool_calls += 1
                if tool_calls > self._limits.max_tool_calls:
                    run.limit_hit, run.result = (
                        "max_tool_calls",
                        _fallback("tool-call limit reached"),
                    )
                    return
                messages.append(await self._tool_message(call, executor))
        run.limit_hit, run.result = "max_turns", _fallback("turn limit reached")

    async def _tool_message(self, call: ToolCall, executor: ToolExecutor) -> ChatMessage:
        if call.name == SUBMIT:
            payload: dict[str, Any] = {
                "ok": False,
                "error": {"code": "VALIDATION_ERROR", "message": "result did not match the schema"},
            }
        else:
            payload = await executor.execute(call)
        text = UntrustedText(json.dumps(payload, ensure_ascii=False, default=str))
        return ChatMessage(
            "tool",
            wrap_untrusted("tool_result", text, self._block_ids()),
            tool_call_id=call.call_id,
        )


def _specs() -> tuple[ToolSpec, ...]:
    submit = ToolSpec(
        SUBMIT,
        "Submit the final result. Call exactly once, last.",
        OrderActionsResult.model_json_schema(),
    )
    return (*(t.spec() for t in TOOLS.values()), submit)


def _parse_result(call: ToolCall) -> OrderActionsResult | None:
    try:
        return OrderActionsResult.model_validate(call.arguments)
    except ValidationError:
        return None


def _consistent(result: OrderActionsResult, log: list[dict[str, Any]]) -> OrderActionsResult:
    """Code check: 'pending approval' is only claimed when a write is actually pending."""
    pending = any(
        step["result"].get("ok") and step["result"]["data"].get("status") == "pending_approval"
        for step in log
    )
    if result.outcome is Outcome.PENDING_HUMAN_APPROVAL and not pending:
        return _fallback("claimed a pending approval that was never submitted")
    return result


def _fallback(why: str) -> OrderActionsResult:
    return OrderActionsResult(
        outcome=Outcome.CANNOT_HELP,
        actions=[],
        customer_reply=HANDOFF_REPLY,
        needs_human=True,
        reason=f"Agent stopped: {why}.",
    )
