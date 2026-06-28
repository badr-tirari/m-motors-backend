from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables (.env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    secret_key: str = "change-me-to-a-random-secret-in-production"
    access_token_expire_minutes: int = 30
    upload_dir: str = "./uploads"


settings = Settings()
