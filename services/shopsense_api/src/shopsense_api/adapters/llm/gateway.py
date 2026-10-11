"""In-process LLM gateway (D4): routes agent profiles to providers, falls back on
transient provider errors, and meters tokens per call.

Refusals and invalid output are not retried on another provider: the caller decides
(triage retries once, then fails closed).
"""

import time
from collections.abc import Mapping
from dataclasses import dataclass

import structlog
from pydantic import BaseModel

from shopsense_api.adapters.llm.provider import ModelProvider, ModelRoute, ProviderError
from shopsense_api.application.ports.llm import StructuredRequest, StructuredResponse
from shopsense_api.domain.exceptions import LLMUnavailable

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AgentProfile:
    routes: tuple[ModelRoute, ...]


class LLMGateway:
    def __init__(
        self, profiles: Mapping[str, AgentProfile], providers: Mapping[str, ModelProvider]
    ) -> None:
        self._profiles = dict(profiles)
        self._providers = dict(providers)

    async def generate_structured[T: BaseModel](
        self, request: StructuredRequest[T]
    ) -> StructuredResponse[T]:
        profile = self._profiles[request.profile]
        failures: list[str] = []
        for route in profile.routes:
            provider = self._providers.get(route.provider)
            if provider is None:
                failures.append(f"{route.provider}: not configured")
                continue
            try:
                return await self._call(provider, route, request)
            except ProviderError as exc:
                failures.append(f"{route.provider}: {exc}")
                if not exc.transient:
                    break
        raise LLMUnavailable("; ".join(failures) or "no routes configured")

    def with_primary(self, provider_name: str) -> "LLMGateway":
        """Return a gateway whose profiles try the named provider first (demos, comparisons)."""
        reordered = {
            name: AgentProfile(tuple(sorted(p.routes, key=lambda r: r.provider != provider_name)))
            for name, p in self._profiles.items()
        }
        return LLMGateway(reordered, self._providers)

    async def _call[T: BaseModel](
        self, provider: ModelProvider, route: ModelRoute, request: StructuredRequest[T]
    ) -> StructuredResponse[T]:
        started = time.perf_counter()
        response = await provider.generate(route, request)
        log.info(
            "llm_call",
            profile=request.profile,
            provider=response.provider,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        return response
