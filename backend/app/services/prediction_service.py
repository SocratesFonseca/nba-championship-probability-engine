from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from app.core.config import settings
from app.services.baseline_model import (
    LEAKAGE_PATTERNS,
    PROBABILITY_COLUMN,
    TARGET_COLUMN,
    normalize_season_probabilities,
    season_start_year,
)

MODEL_FILENAME = "logistic_baseline_pipeline.joblib"
METADATA_FILENAME = "logistic_baseline_metadata.json"
SEASON_PATTERN = re.compile(r"^\d{4}-\d{2}$")


class PredictionServiceError(Exception):
    pass


class ModelUnavailableError(PredictionServiceError):
    pass


class SeasonUnavailableError(PredictionServiceError):
    pass


class InvalidSeasonError(PredictionServiceError):
    pass


@dataclass(frozen=True)
class ModelBundle:
    pipeline: Pipeline
    metadata: dict[str, Any]
    features: tuple[str, ...]


def validate_season_label(season: str) -> str:
    if not SEASON_PATTERN.fullmatch(season):
        raise InvalidSeasonError("Season must use NBA format such as 2023-24.")

    start_year = season_start_year(season)
    expected_end = str(start_year + 1)[-2:]
    if season[-2:] != expected_end:
        raise InvalidSeasonError("Season end year must follow the start year.")

    return season


def _artifact_paths() -> tuple[Path, Path]:
    output_dir = settings.resolved_nba_model_output_dir
    return output_dir / MODEL_FILENAME, output_dir / METADATA_FILENAME


def _validate_metadata(metadata: dict[str, Any]) -> tuple[str, ...]:
    required = (
        "model_version",
        "model_type",
        "training_cutoff",
        "features",
        "evaluation_metrics",
        "generated_at",
    )
    missing = [field for field in required if field not in metadata]
    if missing:
        raise ModelUnavailableError(
            "Model metadata is missing required fields: " + ", ".join(missing)
        )

    features = tuple(metadata["features"])
    if not features:
        raise ModelUnavailableError("Model metadata has no feature allowlist.")

    blocked = [
        feature
        for feature in features
        if feature == TARGET_COLUMN
        or any(pattern in feature.lower() for pattern in LEAKAGE_PATTERNS)
    ]
    if blocked:
        raise ModelUnavailableError(
            "Model feature allowlist contains leakage-prone fields."
        )

    return features


@lru_cache(maxsize=1)
def load_model_bundle() -> ModelBundle:
    model_path, metadata_path = _artifact_paths()
    if not model_path.exists() or not metadata_path.exists():
        raise ModelUnavailableError("Trained model artifacts are unavailable.")

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        pipeline = joblib.load(model_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ModelUnavailableError("Trained model artifacts are invalid.") from exc
    except Exception as exc:
        raise ModelUnavailableError("Trained model artifacts could not be loaded.") from exc

    if not isinstance(pipeline, Pipeline) or not hasattr(pipeline, "predict_proba"):
        raise ModelUnavailableError("Model artifact is not a probability pipeline.")

    features = _validate_metadata(metadata)
    pipeline_features = tuple(getattr(pipeline, "feature_names_in_", ()))
    if pipeline_features and pipeline_features != features:
        raise ModelUnavailableError(
            "Model artifact and metadata feature allowlists are incompatible."
        )

    return ModelBundle(pipeline=pipeline, metadata=metadata, features=features)


def clear_prediction_caches() -> None:
    load_model_bundle.cache_clear()
    load_processed_data.cache_clear()


def _dataset_paths() -> tuple[Path, Path]:
    processed_dir = settings.resolved_nba_processed_dir
    return (
        processed_dir / "team_season_training.csv",
        processed_dir / "heldout" / "team_season_training.csv",
    )


@lru_cache(maxsize=1)
def load_processed_data() -> pd.DataFrame:
    dataset_paths = _dataset_paths()
    existing = [path for path in dataset_paths if path.exists()]
    if not existing:
        raise SeasonUnavailableError("Processed team-season data is unavailable.")

    try:
        frames = [pd.read_csv(path) for path in existing]
    except (OSError, ValueError) as exc:
        raise SeasonUnavailableError("Processed team-season data is invalid.") from exc

    frame = pd.concat(frames, ignore_index=True)
    if frame.empty:
        raise SeasonUnavailableError("Processed team-season data is empty.")
    if frame.duplicated(["season", "team_id"]).any():
        raise SeasonUnavailableError("Processed data has duplicate team-season rows.")

    return frame


def get_model_status() -> dict[str, Any]:
    try:
        bundle = load_model_bundle()
    except ModelUnavailableError as exc:
        return {
            "available": False,
            "features": [],
            "message": str(exc),
        }

    metadata = bundle.metadata
    return {
        "available": True,
        "model_version": metadata["model_version"],
        "model_type": metadata["model_type"],
        "training_cutoff": metadata["training_cutoff"],
        "features": list(bundle.features),
        "evaluation_metrics": metadata["evaluation_metrics"],
        "generated_at": metadata["generated_at"],
        "message": "Trained model is available.",
    }


def _data_type(season: str, metadata: dict[str, Any]) -> str:
    splits = metadata.get("splits", {})
    validation = splits.get("validation", {})
    test = splits.get("test", {})
    season_year = season_start_year(season)

    if validation and season_start_year(validation["start"]) <= season_year <= season_start_year(validation["end"]):
        return "historical validation prediction"
    if test and season_start_year(test["start"]) <= season_year <= season_start_year(test["end"]):
        return "historical holdout prediction"
    return "historical training-period inference"


def predict_season(season: str) -> dict[str, Any]:
    validate_season_label(season)
    bundle = load_model_bundle()
    all_rows = load_processed_data()
    season_rows = all_rows[all_rows["season"].astype(str) == season].copy()
    if season_rows.empty:
        raise SeasonUnavailableError(f"No processed team data is available for {season}.")

    missing = [feature for feature in bundle.features if feature not in season_rows.columns]
    if missing:
        raise ModelUnavailableError(
            "Processed data is incompatible with the model feature allowlist."
        )
    entirely_missing = [
        feature
        for feature in bundle.features
        if season_rows[feature].isna().all()
    ]
    if entirely_missing:
        raise ModelUnavailableError(
            "Processed data is incompatible with the model feature allowlist."
        )
    if TARGET_COLUMN in bundle.features:
        raise ModelUnavailableError("Target leakage was found in model features.")
    if season_rows[list(bundle.features)].shape[1] != len(bundle.features):
        raise ModelUnavailableError("Model feature selection is incompatible.")

    try:
        raw_scores = bundle.pipeline.predict_proba(
            season_rows[list(bundle.features)]
        )[:, 1]
    except Exception as exc:
        raise ModelUnavailableError(
            "Model could not score the processed season data."
        ) from exc

    predictions = normalize_season_probabilities(season_rows, raw_scores)
    if predictions["team_id"].duplicated().any():
        raise SeasonUnavailableError("A team appears more than once in the season.")
    if (predictions[PROBABILITY_COLUMN] < 0).any():
        raise ModelUnavailableError("Model returned a negative probability.")
    if not np.isclose(predictions[PROBABILITY_COLUMN].sum(), 1.0, atol=1e-12):
        raise ModelUnavailableError("Season probabilities do not sum to 1.0.")

    ranked = predictions.sort_values(
        [PROBABILITY_COLUMN, "team_id"],
        ascending=[False, True],
    ).reset_index(drop=True)
    if not ranked[PROBABILITY_COLUMN].is_monotonic_decreasing:
        raise ModelUnavailableError("Prediction rankings are inconsistent.")

    teams = []
    for index, row in ranked.iterrows():
        teams.append(
            {
                "rank": index + 1,
                "team_id": int(row["team_id"]),
                "team_name": str(row["team_name"]),
                "championship_probability": float(row[PROBABILITY_COLUMN]),
                "actual_champion": bool(row[TARGET_COLUMN]),
            }
        )

    metadata = bundle.metadata
    return {
        "season": season,
        "data_type": _data_type(season, metadata),
        "model_version": metadata["model_version"],
        "training_cutoff": metadata["training_cutoff"],
        "generated_at": metadata["generated_at"],
        "teams": teams,
    }


def latest_available_season() -> str:
    frame = load_processed_data()
    seasons = sorted(
        frame["season"].dropna().astype(str).unique(),
        key=season_start_year,
    )
    if not seasons:
        raise SeasonUnavailableError("No processed seasons are available.")
    return seasons[-1]
