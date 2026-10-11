"""Tool-calling LLM port (M2). Separate from LLMClient so use cases depend only on the
capability they use. Messages and tool calls are provider-neutral; adapters translate."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from shopsense_api.application.ports.llm import TokenUsage


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema of the arguments


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str = ""  # kept when the model emitted invalid JSON


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True, slots=True)
class ToolTurnRequest:
    profile: str
    system_prompt: str
    messages: tuple[ChatMessage, ...]
    tools: tuple[ToolSpec, ...]


@dataclass(frozen=True, slots=True)
class ToolTurn:
    content: str
    tool_calls: tuple[ToolCall, ...]
    provider: str
    model: str
    usage: TokenUsage


class ToolCallingLLM(Protocol):
    async def complete_with_tools(self, request: ToolTurnRequest) -> ToolTurn:
        """One model turn: text and/or tool calls. Raises LLMRefused or LLMUnavailable."""
        ...
