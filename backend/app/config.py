"""Centralised, type-safe configuration loaded from environment / .env.

Everything that varies between dev, CI and prod lives here so the rest of the
codebase never reads os.environ directly.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM ---
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model_fast: str = "gemini-2.5-flash"
    gemini_model_smart: str = "gemini-2.5-pro"
    llm_thinking_budget: int = 2048

    # --- Sandbox (test execution) ---
    sandbox_enabled: bool = True
    sandbox_backend: str = "auto"  # auto | docker | local
    sandbox_timeout: int = 120

    # --- Database ---
    database_url: str = "postgresql+asyncpg://codegen:codegen@localhost:5432/codegen"

    # --- GitHub App ---
    github_app_id: str = ""
    github_webhook_secret: str = ""
    github_private_key_path: str = "./github-app-private-key.pem"

    # --- App ---
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — import this everywhere instead of constructing Settings()."""
    return Settings()
