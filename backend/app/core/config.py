from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "Group Scheduling API"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./group_scheduling.db"
    allowed_origins: str = "http://localhost:5173"
    auto_create_tables: bool = True
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    app_session_secret: str = "change-me-before-deployment"
    session_cookie_name: str = "group_scheduler_session"
    session_cookie_secure: bool = False
    frontend_base_url: str = "http://localhost:5173"
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

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

