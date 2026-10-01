from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./spiderfinance.db"
    secret_key: str = "development-only-change-me-at-least-32-characters"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    access_token_minutes: int = 60 * 24

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
