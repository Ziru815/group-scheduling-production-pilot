from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_environment: Literal["development", "test", "production"] = "development"
    app_name: str = "Group Scheduling API"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./group_scheduling.db"
    allowed_origins: str = "http://localhost:5173"
    auto_create_tables: bool = True
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_oauth_transaction_cookie_name: str = "google_oauth_transaction"
    google_oauth_transaction_max_age_seconds: int = 600
    app_session_secret: str = "change-me-before-deployment"
    session_cookie_name: str = "group_scheduler_session"
    session_cookie_secure: bool = False
    frontend_base_url: str = "http://localhost:5173"
    static_dir: str | None = None
    debug_auth_enabled: bool = False
    use_mock_providers: bool = False
    onemap_base_url: str = "https://www.onemap.gov.sg/api"
    onemap_token: str | None = None
    onemap_email: str | None = None
    onemap_password: str | None = None
    data_gov_sg_base_url: str = "https://api-open.data.gov.sg"
    lta_account_key: str | None = None
    default_journey_cap_minutes: int = 60
    default_minimum_attendees: int = 2
    default_shortlist_size: int = 10
    default_participant_limit: int = 12
    default_timeslot_step_minutes: int = 15

    @field_validator("database_url", mode="before")
    @classmethod
    def select_psycopg_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    def validate_runtime(self) -> None:
        if self.app_environment != "production":
            return
        if self.app_session_secret == "change-me-before-deployment" or len(self.app_session_secret) < 32:
            raise ValueError("APP_SESSION_SECRET must be a non-default value of at least 32 characters")
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg in production")
        if self.auto_create_tables:
            raise ValueError("AUTO_CREATE_TABLES must be false in production")
        if self.debug_auth_enabled:
            raise ValueError("DEBUG_AUTH_ENABLED must be false in production")
        if self.use_mock_providers:
            raise ValueError("USE_MOCK_PROVIDERS must be false in production")
        if not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be true in production")
        if not self.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID is required in production")
        if not self.google_client_secret:
            raise ValueError("GOOGLE_CLIENT_SECRET is required in production")
        if not self.onemap_token and not (self.onemap_email and self.onemap_password):
            raise ValueError("ONEMAP_TOKEN or ONEMAP_EMAIL and ONEMAP_PASSWORD are required in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

