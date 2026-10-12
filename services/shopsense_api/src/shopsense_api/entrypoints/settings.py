"""Typed settings from environment variables / .env (entrypoints layer only)."""

from enum import StrEnum
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[5]


class AuthMode(StrEnum):
    ENTRA = "entra"  # managed identity / developer login (default; no keys)
    KEY = "key"  # local development fallback only


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SHOPSENSE_", env_file=REPO_ROOT / ".env", extra="ignore"
    )

    auth_mode: AuthMode = AuthMode.ENTRA
    # OAuth scope for Entra tokens; not a secret
    token_scope: str = "https://cognitiveservices.azure.com/.default"  # noqa: S105
    foundry_resource: str = ""
    foundry_api_key: SecretStr | None = None

    # Model gateway (APIM, routes by difficulty tier). Empty = call Foundry directly.
    model_gateway_url: str = ""
    model_gateway_key: SecretStr | None = None
    model_tier: str = "standard"

    # Primary model and a second vendor on the same Foundry resource (D15)
    primary_deployment: str = "gpt-4.1-mini"
    second_vendor_deployment: str = "Llama-3.3-70B-Instruct"
    second_vendor_output_mode: str = "json_object"

    # Claude adapter: enabled only where the subscription has Claude quota
    claude_enabled: bool = False
    claude_deployment: str = "claude-opus-5-5"

    # M6: order tools go through the MCP server (LLD-4); the caller context is signed with this key
    mcp_url: str = "http://localhost:8100"
    context_key: SecretStr = SecretStr("local-development-only-key-change-me")
    order_platform_url: str = "http://localhost:8001"
    order_platform_timeout_s: float = 15.0
    agent_max_tokens: int = 1_500

    triage_effort: str = "low"
    triage_max_tokens: int = 2_000
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 5  # SDK retries 429/5xx with backoff, honouring Retry-After
    log_json: bool = True

    # M3: embeddings, policy index (Qdrant) and the shopsense PostgreSQL database
    embedding_deployment: str = "text-embedding-3-small"
    embedding_dim: int = 1_536
    # Empty URL = Qdrant embedded mode on local disk (no server needed for demos and eval)
    qdrant_url: str = ""
    qdrant_path: str = "data/qdrant-local"
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "policy_chunks_v2"
    # Local cross-encoder for reranking (fastembed ONNX; downloaded once)
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    policy_dir: str = "data/policies"
    # Origins allowed to call the API from a browser (the Angular app; comma-separated in the env)
    cors_origins: list[str] = ["http://localhost:4200"]
    # Signs reviewer approval grants (M8-4); the Order Platform verifies with the same key
    grant_key: SecretStr = SecretStr("local-development-only-key-change-me")
    # M7: local JSONL trace (always) and optional Langfuse ingestion (when keys are set)
    trace_path: str = "traces/shopsense.jsonl"
    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr | None = None
    # Empty URL = no database; memory and policy rules then need one (see infra/m3)
    database_url: str = ""
    db_token_scope: str = "https://ossrdbms-aad.database.windows.net/.default"  # noqa: S105

    @property
    def foundry_openai_base_url(self) -> str:
        return f"https://{self.foundry_resource}.openai.azure.com/openai/v1/"
