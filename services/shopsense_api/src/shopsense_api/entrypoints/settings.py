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
    order_platform_timeout_s: float = 5.0
    agent_max_tokens: int = 1_500

    triage_effort: str = "low"
    triage_max_tokens: int = 2_000
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 5  # SDK retries 429/5xx with backoff, honouring Retry-After
    log_json: bool = True

    @property
    def foundry_openai_base_url(self) -> str:
        return f"https://{self.foundry_resource}.openai.azure.com/openai/v1/"
