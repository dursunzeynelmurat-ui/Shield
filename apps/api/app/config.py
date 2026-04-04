from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://shield:shield@localhost:5432/shield"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    # Storage
    storage_backend: str = "local"  # "local" or "s3"
    local_storage_path: str = "/tmp/shield_uploads"
    s3_bucket: str = ""
    s3_region: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # AI provider
    ai_provider: str = "openai"  # "openai" or "anthropic"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # Monitoring
    price_check_interval_hours: int = 24
    monitoring_duration_days: int = 14

    class Config:
        env_file = ".env"


settings = Settings()
