"""Settings for the MCP server (environment prefix MCP_)."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_CONTEXT_KEY = "local-development-only-key-change-me"


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_", extra="ignore")

    order_platform_url: str = "http://localhost:8001"
    order_platform_timeout_s: float = 15.0
    # Shared with ShopSense; in Azure this comes from Key Vault through managed identity
    context_key: SecretStr = SecretStr(DEV_CONTEXT_KEY)
