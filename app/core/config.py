from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONTROL_TOWER_", env_file=".env", env_file_encoding="utf-8", extra="ignore")
    env: str = "local"
    app_name: str = "Support Escalation Agent Control Tower"
    state_file: Path = Path("data/control_tower_state.db")
    api_keys: str = "demo-control-tower-key"
    demo_api_key: str = "demo-control-tower-key"
    log_level: str = "INFO"
    max_tool_attempts: int = 3
    low_confidence_threshold: float = 0.62
    sla_high_risk_threshold: float = 0.70
    llm_provider: str = "local"

    @property
    def allowed_api_keys(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()} | {self.demo_api_key}


@lru_cache
def get_settings() -> Settings:
    return Settings()
