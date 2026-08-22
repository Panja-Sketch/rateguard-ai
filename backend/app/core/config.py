from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings managed via pydantic-settings with environment variable overrides."""

    app_name: str = "RateGuard AI"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    google_cloud_project: str = "rateguard-ai"
    google_cloud_region: str = "us-central1"
    log_level: str = "INFO"

    # CORS configuration
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # BigQuery Configuration
    bigquery_enabled: bool = False
    bigquery_dataset: str = "rateguard"
    bigquery_portfolio_table: str = "synthetic_policies"
    bigquery_results_table: str = "portfolio_exposure_results"
    bigquery_location: str = "US"

    # Pub/Sub Async Workflow Configuration
    async_enabled: bool = False
    pubsub_topic: str = "assurance-runs"
    pubsub_subscription: str = "assurance-worker"

    model_config = SettingsConfigDict(
        env_prefix="RATEGUARD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings retriever."""
    return Settings()
