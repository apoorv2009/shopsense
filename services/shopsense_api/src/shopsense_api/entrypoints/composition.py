"""Composition root: builds adapters and wires them into use cases (L2f).

`container()` owns every network resource (Entra credential, SDK clients) and closes
them on exit; callers never construct adapters themselves.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, replace

from anthropic import AsyncAnthropicFoundry
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncOpenAI

from shopsense_api.adapters.llm.anthropic_foundry import AnthropicFoundryProvider
from shopsense_api.adapters.llm.foundry_openai import FoundryOpenAIProvider
from shopsense_api.adapters.llm.gateway import AgentProfile, LLMGateway
from shopsense_api.adapters.llm.provider import ModelProvider, ModelRoute
from shopsense_api.adapters.prompts.file_repository import FilePromptRepository
from shopsense_api.application.use_cases.triage_ticket import TriageTicket
from shopsense_api.entrypoints.settings import AuthMode, Settings

PRIMARY = "azure-openai"
SECOND_VENDOR = "foundry-llama"
TokenProvider = Callable[[], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    providers: dict[str, ModelProvider]

    def gateway(self, primary_provider: str | None = None) -> LLMGateway:
        gateway = LLMGateway(build_profiles(self.settings), self.providers)
        return gateway.with_primary(primary_provider) if primary_provider else gateway

    def triage(self, primary_provider: str | None = None) -> TriageTicket:
        return TriageTicket(llm=self.gateway(primary_provider), prompts=FilePromptRepository())


@asynccontextmanager
async def container(settings: Settings) -> AsyncIterator[Container]:
    async with AsyncExitStack() as stack:
        token: TokenProvider | None = None
        if settings.auth_mode is AuthMode.ENTRA:
            credential = await stack.enter_async_context(DefaultAzureCredential())
            token = get_bearer_token_provider(credential, settings.token_scope)
        openai_client, claude_client = build_clients(settings, token)
        for client in (openai_client, claude_client):
            if client is not None:
                stack.push_async_callback(client.close)
        yield Container(settings, build_providers(openai_client, claude_client))


def build_clients(
    settings: Settings, token: TokenProvider | None
) -> tuple[AsyncOpenAI | None, AsyncAnthropicFoundry | None]:
    if not settings.foundry_resource:
        return None, None
    key = settings.foundry_api_key.get_secret_value() if settings.foundry_api_key else None
    openai_client = AsyncOpenAI(base_url=settings.foundry_openai_base_url, api_key=token or key)
    claude_client = (
        AsyncAnthropicFoundry(
            resource=settings.foundry_resource,
            api_key=None if token else key,
            azure_ad_token_provider=token,
        )
        if settings.claude_enabled
        else None
    )
    return openai_client, claude_client


def build_providers(
    openai_client: AsyncOpenAI | None, claude_client: AsyncAnthropicFoundry | None
) -> dict[str, ModelProvider]:
    providers: dict[str, ModelProvider] = {}
    if openai_client is not None:
        providers[PRIMARY] = FoundryOpenAIProvider(PRIMARY, openai_client)
        providers[SECOND_VENDOR] = FoundryOpenAIProvider(SECOND_VENDOR, openai_client)
    if claude_client is not None:
        providers[AnthropicFoundryProvider.name] = AnthropicFoundryProvider(claude_client)
    return providers


def build_profiles(settings: Settings) -> dict[str, AgentProfile]:
    base = ModelRoute(
        provider=PRIMARY,
        model=settings.primary_deployment,
        max_tokens=settings.triage_max_tokens,
        timeout_s=settings.llm_timeout_s,
    )
    second = replace(
        base,
        provider=SECOND_VENDOR,
        model=settings.second_vendor_deployment,
        output_mode=settings.second_vendor_output_mode,
    )
    routes = [base, second]
    if settings.claude_enabled:
        claude = replace(
            base,
            provider=AnthropicFoundryProvider.name,
            model=settings.claude_deployment,
            effort=settings.triage_effort,
        )
        routes.insert(0, claude)
    return {"triage": AgentProfile(tuple(routes))}
