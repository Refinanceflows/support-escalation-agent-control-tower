from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    api_demo_token: str = "dev-demo-token"
    llm_provider: str = "mock"
    database_url: str = "sqlite:///./control_tower.db"
    log_level: str = "INFO"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None
    max_tool_attempts: int = Field(default=2, ge=1, le=5)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def sqlite_path(self) -> Path:
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("Only sqlite persistence is enabled in the local implementation")
        return Path(self.database_url.replace("sqlite:///", "", 1)).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
