from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str | None = None
    frontend_url: str = "http://localhost:5173"
    environment: str = "development"
    nba_data_dir: str | None = None
    nba_api_raw_dir: str | None = None
    nba_processed_dir: str | None = None
    nba_model_output_dir: str | None = None
    nba_prediction_data_path: str | None = None
    nba_api_timeout_seconds: int = 30
    nba_api_request_delay_seconds: float = 1.0
    nba_api_max_retries: int = 3

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
    def resolved_nba_api_raw_dir(self) -> Path:
        if self.nba_api_raw_dir:
            return Path(self.nba_api_raw_dir).expanduser()

        return Path(__file__).resolve().parents[2] / "data" / "raw" / "nba_api"

    @property
    def resolved_nba_processed_dir(self) -> Path:
        if self.nba_processed_dir:
            return Path(self.nba_processed_dir).expanduser()

        return Path(__file__).resolve().parents[2] / "data" / "processed"

    @property
    def resolved_nba_model_output_dir(self) -> Path:
        if self.nba_model_output_dir:
            return Path(self.nba_model_output_dir).expanduser()

        return Path(__file__).resolve().parents[2] / "outputs"

    @property
    def resolved_nba_prediction_data_path(self) -> Path | None:
        if self.nba_prediction_data_path:
            return Path(self.nba_prediction_data_path).expanduser()

        return None

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        if self.is_production:
            return [self.frontend_url.rstrip("/")]

        return ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
