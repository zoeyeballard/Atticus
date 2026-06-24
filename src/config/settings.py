"""Application settings, loaded from environment / .env.

All configuration is centralized here so that secrets and model choices never appear inline in
business logic. Use ``get_settings()`` (cached) rather than instantiating ``Settings`` directly.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration.

    Values are read from environment variables (case-insensitive) or a local ``.env`` file.
    See ``.env.example`` for the full list.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Anthropic ---
    anthropic_api_key: str = Field(default="", description="Anthropic Claude API key")

    # --- Database ---
    database_url: str = Field(
        default="postgresql://atticus:atticus_dev@localhost:5432/atticus",
        description="PostgreSQL (with pgvector) connection string",
    )

    # --- USPTO Open Data Portal ---
    uspto_api_key: str = Field(default="", description="USPTO Open Data Portal API key")
    uspto_base_url: str = Field(
        default="https://api.uspto.gov/api/v1",
        description="USPTO ODP API base URL (includes the /api/v1 prefix)",
    )

    # --- Models ---
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    generation_model: str = Field(default="claude-sonnet-4-6")
    verification_model: str = Field(default="claude-haiku-4-5")
    embedding_dim: int = Field(default=384, description="Dimension of the embedding model output")

    # --- Retrieval ---
    default_top_k: int = Field(default=8, description="Default number of chunks to retrieve")

    # --- Budget controls ---
    max_cost_per_run_usd: float = Field(
        default=0.0,
        description="Hard cap on Anthropic spend per LLMClient instance; 0 disables the cap.",
    )
    enable_prompt_caching: bool = Field(
        default=True,
        description="Cache the (stable) system prompt to cut input-token cost on repeated calls.",
    )

    # --- App ---
    log_level: str = Field(default="INFO")
    audit_trail_enabled: bool = Field(default=True)
    api_prefix: str = Field(default="/api/v1")

    @property
    def anthropic_configured(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def uspto_configured(self) -> bool:
        return bool(self.uspto_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()
