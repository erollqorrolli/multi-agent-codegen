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
    # Both default to Flash because the free tier does NOT include 2.5 Pro
    # (quota is 0). With a paid plan you can set GEMINI_MODEL_SMART=gemini-2.5-pro.
    # The smart tier still reasons harder via a larger thinking budget.
    gemini_model_fast: str = "gemini-2.5-flash"
    gemini_model_smart: str = "gemini-2.5-flash"
    llm_thinking_budget: int = 1024
    llm_thinking_budget_smart: int = 4096
    # Generated projects are large; a low cap truncates the JSON mid-file.
    llm_max_output_tokens: int = 32768

    # --- Pipeline ---
    # Max architect→fix-loop passes. Each iteration adds ~4 LLM calls, so keep
    # this low on the free tier (20 requests/day). Raise it with a paid plan.
    pipeline_max_iterations: int = 2

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
    # Optional API auth. Empty = open (dev/demo). Set in prod to require a token.
    api_token: str = ""
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
