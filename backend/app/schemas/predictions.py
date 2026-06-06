from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ModelStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    model_version: str | None = None
    model_type: str | None = None
    training_cutoff: str | None = None
    features: list[str] = Field(default_factory=list)
    evaluation_metrics: dict[str, Any] | None = None
    generated_at: str | None = None
    message: str


class RankedTeamPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    team_id: int
    team_name: str
    championship_probability: float
    actual_champion: bool | None = None


class SeasonPredictionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    season: str
    data_type: str
    model_version: str
    training_cutoff: str
    generated_at: str
    teams: list[RankedTeamPrediction]
