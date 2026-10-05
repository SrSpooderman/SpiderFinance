from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./spiderfinance.db"
    secret_key: str = "development-only-change-me-at-least-32-characters"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    registration_enabled: bool = True
    access_token_minutes: int = 60 * 24
    superuser_email: str = ""
    superuser_password: str = ""
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""
    smtp_timeout_seconds: float = Field(default=10, gt=0, le=60)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
