from fastapi import APIRouter, HTTPException

from app.schemas.predictions import ModelStatusResponse, SeasonPredictionResponse
from app.services.prediction_service import (
    InvalidSeasonError,
    ModelUnavailableError,
    SeasonUnavailableError,
    get_model_status,
    latest_available_season,
    predict_season,
)

router = APIRouter(tags=["models and predictions"])


@router.get("/models/status", response_model=ModelStatusResponse)
def model_status() -> ModelStatusResponse:
    return ModelStatusResponse.model_validate(get_model_status())


def _prediction_response(season: str) -> SeasonPredictionResponse:
    try:
        return SeasonPredictionResponse.model_validate(predict_season(season))
    except InvalidSeasonError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except SeasonUnavailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.get("/predictions/latest", response_model=SeasonPredictionResponse)
def latest_predictions() -> SeasonPredictionResponse:
    try:
        season = latest_available_season()
    except SeasonUnavailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return _prediction_response(season)


@router.get("/predictions/{season}", response_model=SeasonPredictionResponse)
def season_predictions(season: str) -> SeasonPredictionResponse:
    return _prediction_response(season)
