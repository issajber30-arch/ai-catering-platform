from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: str = "development"
    # Optional until Phase 2 connects the database.
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    test_database_url: str | None = None
    default_currency: str = "ILS"
    business_timezone: str = "Asia/Jerusalem"
    storage_bucket: str = "dish-images"
    anthropic_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
