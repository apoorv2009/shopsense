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
    claude_deployment: str = "claude-opus-5-5"
    claude_api_key: SecretStr | None = None

    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4.1-mini"
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_api_key: SecretStr | None = None

    triage_effort: str = "low"
    triage_max_tokens: int = 2_000
    llm_timeout_s: float = 60.0
    log_json: bool = True
