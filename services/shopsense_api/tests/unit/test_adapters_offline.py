"""Offline adapter checks: prompt loading and provider schema compatibility (no network)."""

from typing import Any, cast

from anthropic.lib._parse._transform import transform_schema
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import TypeAdapter, ValidationError

from shopsense_api.adapters.llm.provider import validation_problems
from shopsense_api.adapters.prompts.file_repository import FilePromptRepository
from shopsense_api.domain.ticket.support_ticket import SupportTicket


def test_triage_prompt_loads_latest_version() -> None:
    prompt = FilePromptRepository().get("triage")
    assert prompt.version == "v2"
    assert FilePromptRepository().get("order_actions").version == "v2"
    assert "untrusted" in prompt.text


def test_schema_accepted_by_openai_strict_mode() -> None:
    fmt = cast("dict[str, Any]", type_to_response_format_param(SupportTicket))
    assert fmt["type"] == "json_schema"
    schema = fmt["json_schema"]["schema"]
    assert set(schema["required"]) == set(SupportTicket.model_fields)


def test_schema_transformable_for_claude_structured_output() -> None:
    schema = transform_schema(TypeAdapter(SupportTicket).json_schema())
    assert schema["type"] == "object"
    assert "issue_type" in schema["properties"]


def test_validation_problems_do_not_echo_input() -> None:
    try:
        SupportTicket.model_validate({"order_id": "SECRET-INJECTION-TEXT"})
    except ValidationError as exc:
        problems = validation_problems(exc)
    assert problems
    assert not any("SECRET-INJECTION-TEXT" in p for p in problems)
