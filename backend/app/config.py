from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, sourced from environment variables / .env.

    Nothing here is a default that fakes a working integration: absent
    credentials must surface as "unavailable", never as a silent mock.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+asyncpg://agentforge:agentforge@localhost:5433/agentforge"
    redis_url: str = "redis://localhost:6380/0"

    default_llm_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    github_token: str | None = None
    github_repo: str | None = None

    n8n_webhook_url: str | None = None
    slack_webhook_url: str | None = None

    # Additional CORS origin to allow beyond the local dev default (e.g. the
    # deployed frontend's real origin) — comma-separated if more than one.
    extra_cors_origins: str | None = None

    langsmith_api_key: str | None = None
    langsmith_project: str = "agentforge"

    otel_exporter_otlp_endpoint: str | None = None

    max_agent_iterations: int = 6
    max_workflow_seconds: int = 900
    max_run_budget_usd: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
