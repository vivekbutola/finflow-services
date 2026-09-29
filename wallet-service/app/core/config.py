from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # --- App ---
    APP_NAME: str = "wallet-service"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- Database ---
    DATABASE_URL: str = Field(
        ..., description="postgresql+asyncpg://user:pass@host:port/db"
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # --- JWT (validation only — this service never issues tokens) ---
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "auth-service"
    JWT_AUDIENCE: str = "fintech-platform"

    # --- Wallet business rules ---
    # This is intentionally not user-configurable per-currency: the
    # database CHECK constraint (ck_wallets_currency_inr_only) hardcodes
    # 'INR'. This validator makes a misconfiguration fail fast at process
    # startup instead of surfacing as an unhandled IntegrityError the first
    # time a wallet is created.
    WALLET_DEFAULT_CURRENCY: str = "INR"

    @field_validator("WALLET_DEFAULT_CURRENCY")
    @classmethod
    def validate_currency_is_inr(cls, v: str) -> str:
        if v != "INR":
            raise ValueError(
                "WALLET_DEFAULT_CURRENCY must be 'INR' — this matches the "
                "database CHECK constraint and is not currently configurable"
            )
        return v

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the 'postgresql+asyncpg://' driver scheme"
            )
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
