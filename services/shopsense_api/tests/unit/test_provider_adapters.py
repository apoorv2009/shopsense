"""Provider adapters: response mapping and error translation, with fake SDK clients."""

from types import SimpleNamespace
from typing import Any, cast

import anthropic
import httpx2
import openai
import pytest
from pydantic import ValidationError

from shopsense_api.adapters.llm.anthropic_foundry import AnthropicFoundryProvider
from shopsense_api.adapters.llm.foundry_openai import FoundryOpenAIProvider
from shopsense_api.adapters.llm.provider import ModelRoute, ProviderError
from shopsense_api.application.ports.llm import StructuredRequest
from shopsense_api.domain.exceptions import LLMOutputInvalid, LLMRefused
from shopsense_api.domain.ticket.support_ticket import SupportTicket

from support import make_ticket

ROUTE = ModelRoute(provider="p", model="m", max_tokens=100, timeout_s=5, effort="low")
REQUEST = StructuredRequest(
    profile="triage", system_prompt="s", user_message="u", output_type=SupportTicket
)
HTTP_REQUEST = httpx2.Request("POST", "https://example.test")


class FakeClient:
    """Mimics `client.with_options(...).<resource>.parse(...)` for both SDKs."""

    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.kwargs: dict[str, Any] = {}
        self.messages = self
        self.chat = SimpleNamespace(completions=self)
        self.create = self.parse

    def with_options(self, **_: object) -> "FakeClient":
        return self

    async def parse(self, **kwargs: Any) -> object:
        self.kwargs = kwargs
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def claude(outcome: object) -> tuple[AnthropicFoundryProvider, FakeClient]:
    client = FakeClient(outcome)
    return AnthropicFoundryProvider(cast("anthropic.AsyncAnthropicFoundry", client)), client


def gpt(outcome: object) -> FoundryOpenAIProvider:
    return FoundryOpenAIProvider("azure-openai", cast("openai.AsyncOpenAI", FakeClient(outcome)))


def claude_message(stop_reason: str, parsed: object) -> SimpleNamespace:
    usage = SimpleNamespace(input_tokens=11, output_tokens=7)
    return SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed, usage=usage)


def validation_error() -> ValidationError:
    try:
        SupportTicket.model_validate({})
    except ValidationError as exc:
        return exc
    raise AssertionError


async def test_claude_success_sends_effort_and_maps_usage() -> None:
    provider, client = claude(claude_message("end_turn", make_ticket()))
    response = await provider.generate(ROUTE, REQUEST)
    assert response.provider == "claude-foundry"
    assert response.usage.input_tokens == 11
    assert client.kwargs["output_config"] == {"effort": "low"}
    assert client.kwargs["output_format"] is SupportTicket


@pytest.mark.parametrize(
    ("message", "error"),
    [
        (claude_message("refusal", None), LLMRefused),
        (claude_message("max_tokens", None), LLMOutputInvalid),
        (validation_error(), LLMOutputInvalid),
    ],
)
async def test_claude_failures_are_translated(message: object, error: type[Exception]) -> None:
    provider, _ = claude(message)
    with pytest.raises(error):
        await provider.generate(ROUTE, REQUEST)


async def test_claude_transient_and_permanent_errors() -> None:
    provider, _ = claude(anthropic.APIConnectionError(request=HTTP_REQUEST))
    with pytest.raises(ProviderError) as transient:
        await provider.generate(ROUTE, REQUEST)
    assert transient.value.transient
    response = httpx2.Response(401, request=HTTP_REQUEST)
    provider, _ = claude(anthropic.AuthenticationError("no", response=response, body=None))
    with pytest.raises(ProviderError) as permanent:
        await provider.generate(ROUTE, REQUEST)
    assert not permanent.value.transient


def gpt_completion(parsed: object, refusal: str | None = None) -> SimpleNamespace:
    message = SimpleNamespace(parsed=parsed, refusal=refusal)
    usage = SimpleNamespace(prompt_tokens=20, completion_tokens=9)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


async def test_openai_success() -> None:
    response = await gpt(gpt_completion(make_ticket())).generate(ROUTE, REQUEST)
    assert response.provider == "azure-openai"
    assert response.usage.output_tokens == 9


@pytest.mark.parametrize(
    ("outcome", "error"),
    [
        (gpt_completion(None, refusal="no"), LLMRefused),
        (gpt_completion(None), LLMOutputInvalid),
        (validation_error(), LLMOutputInvalid),
        (openai.ContentFilterFinishReasonError(), LLMRefused),
        (openai.APIConnectionError(request=HTTP_REQUEST), ProviderError),
    ],
)
async def test_openai_failures_are_translated(outcome: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        await gpt(outcome).generate(ROUTE, REQUEST)


JSON_ROUTE = ModelRoute(
    provider="p", model="llama", max_tokens=100, timeout_s=5, output_mode="json_object"
)


def json_completion(content: str | None, finish_reason: str = "stop") -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    usage = SimpleNamespace(prompt_tokens=3, completion_tokens=4)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], usage=usage)


async def test_json_object_mode_validates_with_pydantic() -> None:
    client = FakeClient(json_completion(make_ticket().model_dump_json()))
    provider = FoundryOpenAIProvider("foundry-llama", cast("openai.AsyncOpenAI", client))
    response = await provider.generate(JSON_ROUTE, REQUEST)
    assert response.provider == "foundry-llama"
    assert client.kwargs["response_format"] == {"type": "json_object"}
    assert "JSON object matching this schema" in client.kwargs["messages"][0]["content"]


@pytest.mark.parametrize(
    ("completion", "error"),
    [
        (json_completion('{"issue_type": "nonsense"}'), LLMOutputInvalid),
        (json_completion(None, "length"), LLMOutputInvalid),
        (json_completion("{}", "content_filter"), LLMRefused),
    ],
)
async def test_json_object_mode_failures(completion: object, error: type[Exception]) -> None:
    provider = FoundryOpenAIProvider("m", cast("openai.AsyncOpenAI", FakeClient(completion)))
    with pytest.raises(error):
        await provider.generate(JSON_ROUTE, REQUEST)
