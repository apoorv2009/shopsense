"""Composition root: builds adapters and wires them into use cases (L2f).

`container()` owns every network resource (Entra credential, SDK clients, database engine,
Qdrant client) and closes them on exit; callers never construct adapters themselves.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import httpx
from anthropic import AsyncAnthropicFoundry
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from langgraph.checkpoint.base import BaseCheckpointSaver
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shopsense_api.adapters.db.sql_stores import SqlMemoryStore, SqlOutboxStore, SqlPolicyStore
from shopsense_api.adapters.llm.anthropic_foundry import AnthropicFoundryProvider
from shopsense_api.adapters.llm.foundry_openai import FoundryOpenAIProvider
from shopsense_api.adapters.llm.gateway import AgentProfile, LLMGateway
from shopsense_api.adapters.llm.provider import ModelProvider, ModelRoute
from shopsense_api.adapters.orders.mcp_order_tools import McpOrderTools
from shopsense_api.adapters.policy.fastembed_reranker import FastEmbedReranker
from shopsense_api.adapters.policy.foundry_embedder import FoundryEmbedder
from shopsense_api.adapters.policy.qdrant_index import QdrantPolicyIndex
from shopsense_api.adapters.prompts.file_repository import FilePromptRepository
from shopsense_api.adapters.tracing.composite import CompositeTracer
from shopsense_api.adapters.tracing.jsonl import JsonlTracer
from shopsense_api.adapters.tracing.langfuse import LangfuseTracer
from shopsense_api.adapters.workflow.langgraph_ticket import build_graph
from shopsense_api.adapters.workflow.runner import TicketRunner
from shopsense_api.application.agents.escalation_reviewer import EscalationReviewer
from shopsense_api.application.agents.order_actions import OrderActionsAgent
from shopsense_api.application.ports.memory import MemoryStore
from shopsense_api.application.ports.orders import OrderTools
from shopsense_api.application.ports.outbox import OutboxStore
from shopsense_api.application.ports.policy import Embedder, PolicyIndex, PolicyStore, Reranker
from shopsense_api.application.ports.tracing import Tracer
from shopsense_api.application.use_cases.answer_policy import AnswerPolicyQuestion
from shopsense_api.application.use_cases.decide_return import DecideReturn
from shopsense_api.application.use_cases.drain_outbox import DrainOutbox
from shopsense_api.application.use_cases.hybrid_search import HybridSearch
from shopsense_api.application.use_cases.ingest_policies import IngestPolicies
from shopsense_api.application.use_cases.judge_groundedness import GroundednessJudge
from shopsense_api.application.use_cases.memory import RecallCustomer, RememberTicket
from shopsense_api.application.use_cases.triage_ticket import TriageTicket
from shopsense_api.application.workflow.flow import TicketFlow
from shopsense_api.domain.policy.grounding import numbers_in
from shopsense_api.domain.policy.model import PolicyDocument
from shopsense_api.entrypoints.settings import AuthMode, Settings

PRIMARY = "azure-openai"
SECOND_VENDOR = "foundry-llama"
TokenProvider = Callable[[], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    providers: dict[str, ModelProvider]
    order_http: httpx.AsyncClient
    embeddings: AsyncOpenAI | None
    qdrant: AsyncQdrantClient | None
    engine: AsyncEngine | None
    sessions: async_sessionmaker[AsyncSession] | None
    langfuse_tracer: LangfuseTracer | None = None

    def gateway(self, primary_provider: str | None = None) -> LLMGateway:
        gateway = LLMGateway(build_profiles(self.settings), self.providers)
        return gateway.with_primary(primary_provider) if primary_provider else gateway

    def triage(self, primary_provider: str | None = None) -> TriageTicket:
        return TriageTicket(llm=self.gateway(primary_provider), prompts=FilePromptRepository())

    def order_actions(self, primary_provider: str | None = None) -> OrderActionsAgent:
        return OrderActionsAgent(
            llm=self.gateway(primary_provider),
            prompts=FilePromptRepository(),
            tools=self.order_tools(),
        )

    def embedder(self) -> Embedder:
        if self.embeddings is None:
            raise RuntimeError("embeddings need SHOPSENSE_FOUNDRY_RESOURCE")
        return FoundryEmbedder(self.embeddings, self.settings.embedding_deployment)

    def policy_index(self) -> PolicyIndex:
        if self.qdrant is None:
            raise RuntimeError("this process was started without the policy index")
        return QdrantPolicyIndex(
            self.qdrant, self.settings.qdrant_collection, self.settings.embedding_dim
        )

    def policy_store(self) -> PolicyStore:
        return SqlPolicyStore(self._require_db())

    def memory_store(self) -> MemoryStore:
        return SqlMemoryStore(self._require_db())

    def ingest_policies(self) -> IngestPolicies:
        return IngestPolicies(self.policy_store(), self.policy_index(), self.embedder())

    def reranker(self) -> Reranker:
        return FastEmbedReranker(self.settings.rerank_model)

    def search_policy(self) -> HybridSearch:
        return HybridSearch(self.embedder(), self.policy_index(), self.reranker())

    def answer_policy(self, primary_provider: str | None = None) -> AnswerPolicyQuestion:
        return AnswerPolicyQuestion(
            llm=self.gateway(primary_provider),
            prompts=FilePromptRepository(),
            search=self.search_policy(),
        )

    def decide_return(self, corpus: list[PolicyDocument]) -> DecideReturn:
        hashes = {s.chunk_id: s.content_hash for d in corpus for s in d.sections}
        return DecideReturn(self.policy_store(), self.policy_index(), hashes)

    def order_tools(self) -> OrderTools:
        key = self.settings.context_key.get_secret_value().encode("utf-8")
        return McpOrderTools(
            self.settings.mcp_url, key, timeout_s=self.settings.order_platform_timeout_s
        )

    def ticket_runner(
        self,
        corpus: list[PolicyDocument],
        checkpointer: BaseCheckpointSaver[Any],
        orders: OrderTools | None = None,
        tracer: Tracer | None = None,
    ) -> TicketRunner:
        tools = orders or self.order_tools()
        outbox = self.outbox_store()
        grant_key = self.settings.grant_key.get_secret_value().encode("utf-8")
        flow = TicketFlow(
            self.triage(),
            tools,
            self.decide_return(corpus),
            advisor=OrderActionsAgent(
                llm=self.gateway(), prompts=FilePromptRepository(), tools=tools, read_only=True
            ),
            answerer=self.answer_policy(),
            reviewer=EscalationReviewer(self.gateway(), FilePromptRepository()),
            outbox=outbox,
            drainer=DrainOutbox(outbox, tools, grant_key),
            grant_key=grant_key,
            policy_numbers=policy_numbers(corpus),
            recall=self.recall(),
            remember=self.remember(),
        )
        return TicketRunner(build_graph(flow, checkpointer, tracer or self.tracer()), outbox)

    def drainer(self) -> DrainOutbox:
        """Sends approved refunds that are still pending (the outbox worker, run in the API)."""
        grant_key = self.settings.grant_key.get_secret_value().encode("utf-8")
        return DrainOutbox(self.outbox_store(), self.order_tools(), grant_key)

    def outbox_store(self) -> OutboxStore:
        return SqlOutboxStore(self._require_db())

    def tracer(self) -> Tracer:
        local = JsonlTracer(Path(self.settings.trace_path))
        if self.langfuse_tracer is None:
            return local
        return CompositeTracer(local, self.langfuse_tracer)

    def judge(self, primary_provider: str | None = None) -> GroundednessJudge:
        return GroundednessJudge(self.gateway(primary_provider), FilePromptRepository())

    def recall(self) -> RecallCustomer:
        return RecallCustomer(self.memory_store())

    def remember(self) -> RememberTicket:
        return RememberTicket(self.memory_store())

    def _require_db(self) -> async_sessionmaker[AsyncSession]:
        if self.sessions is None:
            raise RuntimeError("memory and policy rules need SHOPSENSE_DATABASE_URL")
        return self.sessions


@asynccontextmanager
async def container(settings: Settings, *, qdrant: bool = True) -> AsyncIterator[Container]:
    async with AsyncExitStack() as stack:
        token: TokenProvider | None = None
        if settings.auth_mode is AuthMode.ENTRA:
            credential = await stack.enter_async_context(DefaultAzureCredential())
            token = get_bearer_token_provider(credential, settings.token_scope)
        openai_client, claude_client = build_clients(settings, token)
        for client in (openai_client, claude_client):
            if client is not None:
                stack.push_async_callback(client.close)
        order_http = httpx.AsyncClient(
            base_url=settings.order_platform_url, timeout=settings.order_platform_timeout_s
        )
        stack.push_async_callback(order_http.aclose)
        qdrant_client = build_qdrant(settings) if qdrant else None
        if qdrant_client is not None:
            stack.push_async_callback(qdrant_client.close)
        engine = await build_database(settings, stack)
        sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        langfuse = await build_langfuse(settings, stack)
        yield Container(
            settings=settings,
            providers=build_providers(openai_client, claude_client),
            order_http=order_http,
            embeddings=openai_client,
            qdrant=qdrant_client,
            engine=engine,
            sessions=sessions if engine is not None else None,
            langfuse_tracer=langfuse,
        )


async def build_langfuse(settings: Settings, stack: AsyncExitStack) -> LangfuseTracer | None:
    """Langfuse ingestion is on only when host and keys are all set (M7-1)."""
    if not (settings.langfuse_host and settings.langfuse_secret_key):
        return None
    client = httpx.AsyncClient(base_url=settings.langfuse_host, timeout=10.0)
    stack.push_async_callback(client.aclose)
    return LangfuseTracer(
        client, settings.langfuse_public_key, settings.langfuse_secret_key.get_secret_value()
    )


def build_qdrant(settings: Settings) -> AsyncQdrantClient:
    if settings.qdrant_url:
        key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        return AsyncQdrantClient(url=settings.qdrant_url, api_key=key)
    return AsyncQdrantClient(path=settings.qdrant_path)


async def build_database(settings: Settings, stack: AsyncExitStack) -> AsyncEngine | None:
    if not settings.database_url:
        return None
    connect_args: dict[str, str] = {}
    if settings.auth_mode is AuthMode.ENTRA:
        credential = await stack.enter_async_context(DefaultAzureCredential())
        access = await credential.get_token(settings.db_token_scope)
        connect_args = {"password": access.token, "ssl": "require"}
    engine = create_async_engine(
        settings.database_url, connect_args=connect_args, pool_pre_ping=True
    )
    stack.push_async_callback(engine.dispose)
    return engine


def build_clients(
    settings: Settings, token: TokenProvider | None
) -> tuple[AsyncOpenAI | None, AsyncAnthropicFoundry | None]:
    if settings.model_gateway_url:
        # Through the model APIM: the gateway holds the Foundry identity and routes by tier
        gateway_key = (
            settings.model_gateway_key.get_secret_value() if settings.model_gateway_key else ""
        )
        gateway_client = AsyncOpenAI(
            base_url=settings.model_gateway_url,
            api_key="managed-by-gateway",  # APIM replaces Authorization with its own identity token
            default_headers={
                "Ocp-Apim-Subscription-Key": gateway_key,
                "x-difficulty": settings.model_tier,
            },
            max_retries=settings.llm_max_retries,
        )
        return gateway_client, None
    if not settings.foundry_resource:
        return None, None
    key = settings.foundry_api_key.get_secret_value() if settings.foundry_api_key else None
    openai_client = AsyncOpenAI(
        base_url=settings.foundry_openai_base_url,
        api_key=token or key,
        max_retries=settings.llm_max_retries,
    )
    claude_client = (
        AsyncAnthropicFoundry(
            resource=settings.foundry_resource,
            api_key=None if token else key,
            azure_ad_token_provider=token,
            max_retries=settings.llm_max_retries,
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
    agent_routes = tuple(replace(r, max_tokens=settings.agent_max_tokens) for r in routes)
    if settings.claude_enabled:
        claude = replace(
            base,
            provider=AnthropicFoundryProvider.name,
            model=settings.claude_deployment,
            effort=settings.triage_effort,
        )
        routes.insert(0, claude)
    return {
        "triage": AgentProfile(tuple(routes)),
        "order_actions": AgentProfile(agent_routes),
        "policy": AgentProfile(tuple(routes)),
        "review": AgentProfile(tuple(routes)),
    }


def policy_numbers(corpus: list[PolicyDocument]) -> frozenset[str]:
    """Every number that appears in the policy corpus: the only policy numbers a reply may use."""
    found: set[str] = set()
    for doc in corpus:
        for section in doc.sections:
            found |= numbers_in(section.text)
    return frozenset(found)
