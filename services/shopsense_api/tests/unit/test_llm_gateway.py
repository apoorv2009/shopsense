import pytest
from pydantic import BaseModel

from shopsense_api.adapters.llm.gateway import AgentProfile, LLMGateway
from shopsense_api.adapters.llm.provider import ModelRoute, ProviderError
from shopsense_api.application.ports.llm import StructuredRequest, StructuredResponse, TokenUsage
from shopsense_api.domain.exceptions import LLMRefused, LLMUnavailable
from shopsense_api.domain.ticket.support_ticket import SupportTicket

from support import make_ticket as make


class FakeProvider:
    def __init__(self, name: str, outcome: Exception | None = None) -> None:
        self.name = name
        self._outcome = outcome
        self.calls = 0

    async def generate[T: BaseModel](
        self, route: ModelRoute, request: StructuredRequest[T]
    ) -> StructuredResponse[T]:
        self.calls += 1
        if self._outcome is not None:
            raise self._outcome
        output = make()
        assert isinstance(output, request.output_type)
        return StructuredResponse(output, self.name, route.model, TokenUsage(1, 1))


def route(provider: str) -> ModelRoute:
    return ModelRoute(provider=provider, model=f"{provider}-model", max_tokens=100, timeout_s=5)


def gateway(*providers: FakeProvider) -> LLMGateway:
    profile = AgentProfile(tuple(route(p.name) for p in providers))
    return LLMGateway({"triage": profile}, {p.name: p for p in providers})


REQUEST = StructuredRequest(
    profile="triage", system_prompt="s", user_message="u", output_type=SupportTicket
)


async def test_uses_primary_provider() -> None:
    primary, secondary = FakeProvider("a"), FakeProvider("b")
    response = await gateway(primary, secondary).generate_structured(REQUEST)
    assert response.provider == "a"
    assert secondary.calls == 0


async def test_falls_back_on_transient_error() -> None:
    primary = FakeProvider("a", ProviderError("RateLimitError", transient=True))
    secondary = FakeProvider("b")
    response = await gateway(primary, secondary).generate_structured(REQUEST)
    assert response.provider == "b"


async def test_non_transient_error_stops_and_reports_unavailable() -> None:
    primary = FakeProvider("a", ProviderError("HTTP 401", transient=False))
    secondary = FakeProvider("b")
    with pytest.raises(LLMUnavailable, match="HTTP 401"):
        await gateway(primary, secondary).generate_structured(REQUEST)
    assert secondary.calls == 0


async def test_refusal_is_not_routed_to_another_provider() -> None:
    primary, secondary = FakeProvider("a", LLMRefused("no")), FakeProvider("b")
    with pytest.raises(LLMRefused):
        await gateway(primary, secondary).generate_structured(REQUEST)
    assert secondary.calls == 0


async def test_all_providers_down() -> None:
    down = ProviderError("APIConnectionError", transient=True)
    with pytest.raises(LLMUnavailable):
        await gateway(FakeProvider("a", down), FakeProvider("b", down)).generate_structured(REQUEST)


async def test_with_primary_reorders_routes() -> None:
    a, b = FakeProvider("a"), FakeProvider("b")
    response = await gateway(a, b).with_primary("b").generate_structured(REQUEST)
    assert response.provider == "b"
    assert a.calls == 0
