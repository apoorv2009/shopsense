"""Order Platform settings (entrypoints layer only)."""

from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[5]


class DbAuth(StrEnum):
    PASSWORD = "password"  # noqa: S105 - auth mode name: local Docker PostgreSQL
    ENTRA = "entra"  # Azure Database for PostgreSQL (no passwords, L9e)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORDER_PLATFORM_", env_file=REPO_ROOT / ".env", extra="ignore"
    )

    database_url: str = "postgresql+asyncpg://shopsense:shopsense@localhost:5432/order_platform"
    db_auth: DbAuth = DbAuth.PASSWORD
    # OAuth scope for Azure PostgreSQL Entra tokens; not a secret
    db_token_scope: str = "https://ossrdbms-aad.database.windows.net/.default"  # noqa: S105
    anchor_date: date | None = None  # seed dates relative to this; None = today
    # Enables /admin/faults for resilience tests; unset = the admin routes do not exist
    admin_token: SecretStr | None = None
    # Verifies reviewer approval grants issued by ShopSense (shared key; Key Vault in Azure)
    grant_key: SecretStr = SecretStr("local-development-only-key-change-me")
    log_json: bool = True
