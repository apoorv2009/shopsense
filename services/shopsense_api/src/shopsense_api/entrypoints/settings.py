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

    # Primary model and a second vendor on the same Foundry resource (D15)
    primary_deployment: str = "gpt-4.1-mini"
    second_vendor_deployment: str = "Llama-3.3-70B-Instruct"
    second_vendor_output_mode: str = "json_object"

    # Claude adapter: enabled only where the subscription has Claude quota
    claude_enabled: bool = False
    claude_deployment: str = "claude-opus-5-5"

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
    qdrant_collection: str = "policy_chunks"
    policy_dir: str = "data/policies"
    # Empty URL = no database; memory and policy rules then need one (see infra/m3)
    database_url: str = ""
    db_token_scope: str = "https://ossrdbms-aad.database.windows.net/.default"  # noqa: S105

    @property
    def foundry_openai_base_url(self) -> str:
        return f"https://{self.foundry_resource}.openai.azure.com/openai/v1/"
