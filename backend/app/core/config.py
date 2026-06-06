from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str | None = None
    frontend_url: str = "http://localhost:5173"
    environment: str = "development"
    nba_data_dir: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def resolved_database_url(self) -> str:
        database_url = self.database_url or "sqlite:///nba_local.db"
        if database_url.startswith("postgres://"):
            return database_url.replace("postgres://", "postgresql://", 1)

        return database_url

    @property
    def resolved_nba_data_dir(self) -> Path:
        if self.nba_data_dir:
            return Path(self.nba_data_dir).expanduser()

        return Path(__file__).resolve().parents[2] / "data" / "raw"

    @property
    def is_data_dir_configured(self) -> bool:
        return self.nba_data_dir is not None

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        if self.is_production:
            return [self.frontend_url]

        return ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
