from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
    )

    PROJECT_NAME: str = "TradeXBot"
    API_V1_PREFIX: str = "/api/v1"

    # MongoDB connection
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "tradexbot"
    # Auto-create indexes on startup
    AUTO_CREATE_TABLES: bool = True

    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ALGORITHM: str = "HS256"

    # Demo: return the password-reset token in the API response (no email service wired up).
    # Set false in production — tokens must only be delivered out-of-band via email.
    EXPOSE_RESET_TOKEN: bool = True
    EXPOSE_FORGOT_PASSWORD_OTP: bool = True
    PASSWORD_RESET_OTP_EXPIRE_MINUTES: int = 10

    SMTP_HOST: str = Field("smtp.gmail.com", env=["SMTP_HOST"])
    SMTP_PORT: int = Field(587, env=["SMTP_PORT"])
    SMTP_USERNAME: str = Field("", env=["SMTP_USERNAME", "EMAIL_USER"])
    SMTP_PASSWORD: str = Field("", env=["SMTP_PASSWORD", "EMAIL_PASS"])
    SMTP_FROM_EMAIL: str = Field("", env=["SMTP_FROM_EMAIL", "EMAIL_USER"])
    SMTP_USE_TLS: bool = Field(True, env=["SMTP_USE_TLS"])

    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    FIRST_ADMIN_EMAIL: str = "admin@tradexbot.com"
    FIRST_ADMIN_PASSWORD: str = "ChangeMe123!"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
