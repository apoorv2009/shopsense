"""Composition root: builds adapters and wires them into use cases (L2f)."""

from anthropic import AsyncAnthropicFoundry
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI
from pydantic import SecretStr

from shopsense_api.adapters.llm.anthropic_foundry import AnthropicFoundryProvider
from shopsense_api.adapters.llm.azure_openai import AzureOpenAIProvider
from shopsense_api.adapters.llm.gateway import AgentProfile, LLMGateway
from shopsense_api.adapters.llm.provider import ModelProvider, ModelRoute
from shopsense_api.adapters.prompts.file_repository import FilePromptRepository
from shopsense_api.application.use_cases.triage_ticket import TriageTicket
from shopsense_api.entrypoints.settings import AuthMode, Settings


def build_providers(settings: Settings) -> dict[str, ModelProvider]:
    providers: dict[str, ModelProvider] = {}
    token_provider = (
        get_bearer_token_provider(DefaultAzureCredential(), settings.token_scope)
        if settings.auth_mode is AuthMode.ENTRA
        else None
    )
    if settings.foundry_resource:
        claude = AsyncAnthropicFoundry(
            resource=settings.foundry_resource,
            api_key=_secret(settings.claude_api_key) if token_provider is None else None,
            azure_ad_token_provider=token_provider,
        )
        providers[AnthropicFoundryProvider.name] = AnthropicFoundryProvider(claude)
    if settings.azure_openai_endpoint:
        gpt = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
            api_key=_secret(settings.azure_openai_api_key) if token_provider is None else None,
            azure_ad_token_provider=token_provider,
        )
        providers[AzureOpenAIProvider.name] = AzureOpenAIProvider(gpt)
    return providers


def build_profiles(settings: Settings) -> dict[str, AgentProfile]:
    triage_routes = (
        ModelRoute(
            provider=AnthropicFoundryProvider.name,
            model=settings.claude_deployment,
            max_tokens=settings.triage_max_tokens,
            timeout_s=settings.llm_timeout_s,
            effort=settings.triage_effort,
        ),
        ModelRoute(
            provider=AzureOpenAIProvider.name,
            model=settings.azure_openai_deployment,
            max_tokens=settings.triage_max_tokens,
            timeout_s=settings.llm_timeout_s,
        ),
    )
    return {"triage": AgentProfile(triage_routes)}


def build_gateway(settings: Settings) -> LLMGateway:
    return LLMGateway(build_profiles(settings), build_providers(settings))


def build_triage(settings: Settings, primary_provider: str | None = None) -> TriageTicket:
    gateway = build_gateway(settings)
    if primary_provider:
        gateway = gateway.with_primary(primary_provider)
    return TriageTicket(llm=gateway, prompts=FilePromptRepository())


def _secret(value: SecretStr | None) -> str | None:
    return value.get_secret_value() if value is not None else None
