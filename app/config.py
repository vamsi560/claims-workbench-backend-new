from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/claims_idp"
    ingest_api_key: str = ""
    frontend_origin: str = "http://localhost:5173"
    guidewire_enabled: bool = False
    guidewire_default_target: str = "cc"
    service_bus_connection_string: str = ""
    service_bus_extract_queue: str = "email-extract"
    service_bus_guidewire_queue: str = "guidewire-submit"
    azure_storage_connection_string: str = ""
    azure_storage_account_url: str = ""
    extract_inline: bool = False
    document_intelligence_endpoint: str = ""
    document_intelligence_key: str = ""
    azure_ai_foundry_endpoint: str = ""
    azure_ai_foundry_key: str = ""
    azure_ai_foundry_deployment: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
