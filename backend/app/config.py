from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    frontend_origin: str = "http://localhost:5173"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_webhook_verify_token: str = ""
    session_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
