"""Composition root: builds adapters and wires them into use cases (L2f)."""

from collections.abc import Awaitable, Callable
from dataclasses import replace

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


def build_providers(settings: Settings) -> dict[str, ModelProvider]:
    if not settings.foundry_resource:
        return {}
    token = _token_provider(settings)
    key = settings.foundry_api_key.get_secret_value() if settings.foundry_api_key else None
    client = AsyncOpenAI(base_url=settings.foundry_openai_base_url, api_key=token or key)
    providers: dict[str, ModelProvider] = {
        PRIMARY: FoundryOpenAIProvider(PRIMARY, client),
        SECOND_VENDOR: FoundryOpenAIProvider(SECOND_VENDOR, client),
    }
    if settings.claude_enabled:
        claude = AsyncAnthropicFoundry(
            resource=settings.foundry_resource,
            api_key=None if token else key,
            azure_ad_token_provider=token,
        )
        providers[AnthropicFoundryProvider.name] = AnthropicFoundryProvider(claude)
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


def build_gateway(settings: Settings) -> LLMGateway:
    return LLMGateway(build_profiles(settings), build_providers(settings))


def build_triage(settings: Settings, primary_provider: str | None = None) -> TriageTicket:
    gateway = build_gateway(settings)
    if primary_provider:
        gateway = gateway.with_primary(primary_provider)
    return TriageTicket(llm=gateway, prompts=FilePromptRepository())


def _token_provider(settings: Settings) -> TokenProvider | None:
    if settings.auth_mode is not AuthMode.ENTRA:
        return None
    return get_bearer_token_provider(DefaultAzureCredential(), settings.token_scope)
