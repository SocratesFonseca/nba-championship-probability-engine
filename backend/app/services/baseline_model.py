from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.services.nba_data_collection import (
    EXCLUDED_LEAKAGE_COLUMNS,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
)

MODEL_VERSION = "logistic-baseline-v1"
TRAIN_END_SEASON = "2006-07"
VALIDATION_START_SEASON = "2007-08"
VALIDATION_END_SEASON = "2010-11"
TEST_START_SEASON = "2011-12"
PROBABILITY_COLUMN = "championship_probability"
RAW_SCORE_COLUMN = "model_score"
FEATURE_ALLOWLIST = tuple(FEATURE_COLUMNS)
LEAKAGE_PATTERNS = (
    "champion",
    "playoff",
    "postseason",
    "finals",
    "target",
    "future",
)
EXCLUDED_MODEL_FIELDS = sorted(
    {
        TARGET_COLUMN,
        *EXCLUDED_LEAKAGE_COLUMNS,
        "playoff_game_log",
        "future_season",
        "target_derived",
    }
)


class ModelTrainingError(Exception):
    pass


def season_start_year(season: str) -> int:
    try:
        return int(str(season).split("-", 1)[0])
    except (TypeError, ValueError):
        raise ModelTrainingError(f"Invalid season label: {season}") from None


def validate_feature_allowlist(
    available_columns: list[str] | pd.Index,
    features: tuple[str, ...] = FEATURE_ALLOWLIST,
) -> None:
    available = set(available_columns)
    missing = [feature for feature in features if feature not in available]
    if missing:
        raise ModelTrainingError(
            "Dataset is missing model features: " + ", ".join(missing)
        )

    blocked = [
        feature
        for feature in features
        if feature == TARGET_COLUMN
        or feature in EXCLUDED_LEAKAGE_COLUMNS
        or any(pattern in feature.lower() for pattern in LEAKAGE_PATTERNS)
    ]
    if blocked:
        raise ModelTrainingError(
            "Leakage-prone fields cannot be model features: " + ", ".join(blocked)
        )


def validate_model_dataset(frame: pd.DataFrame, name: str) -> None:
    required = {"season", "team_id", "team_name", TARGET_COLUMN, *FEATURE_ALLOWLIST}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ModelTrainingError(
            f"{name} dataset is missing columns: {', '.join(missing)}"
        )

    validate_feature_allowlist(frame.columns)

    if frame[["season", "team_id", "team_name"]].isna().any().any():
        raise ModelTrainingError(f"{name} dataset has missing identifiers.")
    if frame.duplicated(["season", "team_id"]).any():
        raise ModelTrainingError(f"{name} dataset has duplicate team-season rows.")

    champion_counts = frame.groupby("season")[TARGET_COLUMN].sum()
    invalid = champion_counts[champion_counts != 1]
    if not invalid.empty:
        raise ModelTrainingError(
            f"{name} dataset does not have exactly one champion in: "
            + ", ".join(invalid.index.astype(str))
        )


def load_model_data(
    historical_path: Path,
    heldout_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not historical_path.exists():
        raise ModelTrainingError(
            f"Historical dataset not found: {historical_path}. "
            "Run python -m app.scripts.collect_nba_data first."
        )
    if not heldout_path.exists():
        raise ModelTrainingError(
            f"Held-out dataset not found: {heldout_path}. "
            "Collect seasons 2011-12 onward before training."
        )

    historical = pd.read_csv(historical_path)
    heldout = pd.read_csv(heldout_path)
    validate_model_dataset(historical, "Historical")
    validate_model_dataset(heldout, "Held-out")

    if tuple(feature for feature in FEATURE_ALLOWLIST if feature in historical.columns) != (
        tuple(feature for feature in FEATURE_ALLOWLIST if feature in heldout.columns)
    ):
        raise ModelTrainingError(
            "Historical and held-out datasets do not share the same feature columns."
        )

    return historical, heldout


def chronological_split(
    historical: pd.DataFrame,
    heldout: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    historical = historical.copy()
    heldout = heldout.copy()
    historical["_season_year"] = historical["season"].map(season_start_year)
    heldout["_season_year"] = heldout["season"].map(season_start_year)

    train = historical[historical["_season_year"] <= season_start_year(TRAIN_END_SEASON)]
    validation = historical[
        historical["_season_year"].between(
            season_start_year(VALIDATION_START_SEASON),
            season_start_year(VALIDATION_END_SEASON),
        )
    ]
    test = heldout[
        heldout["_season_year"] >= season_start_year(TEST_START_SEASON)
    ]

    for name, split in (
        ("training", train),
        ("validation", validation),
        ("test", test),
    ):
        if split.empty:
            raise ModelTrainingError(f"The {name} split is empty.")

    train_seasons = set(train["season"])
    validation_seasons = set(validation["season"])
    test_seasons = set(test["season"])
    if train_seasons & validation_seasons or train_seasons & test_seasons or validation_seasons & test_seasons:
        raise ModelTrainingError("Season overlap was found between model splits.")

    return (
        train.drop(columns="_season_year"),
        validation.drop(columns="_season_year"),
        test.drop(columns="_season_year"),
    )


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=42,
                ),
            ),
        ]
    )


def normalize_season_probabilities(
    frame: pd.DataFrame,
    scores: np.ndarray | pd.Series,
    *,
    score_column: str = RAW_SCORE_COLUMN,
) -> pd.DataFrame:
    output = frame[["season", "team_id", "team_name", TARGET_COLUMN, "win_pct"]].copy()
    output[score_column] = np.clip(np.asarray(scores, dtype=float), 0.0, None)
    season_totals = output.groupby("season")[score_column].transform("sum")
    if (season_totals <= 0).any():
        raise ModelTrainingError("A season has no positive probability score.")

    output[PROBABILITY_COLUMN] = output[score_column] / season_totals
    sums = output.groupby("season")[PROBABILITY_COLUMN].sum()
    if not np.allclose(sums.to_numpy(), 1.0, atol=1e-12):
        raise ModelTrainingError("Season probabilities do not sum to 1.0.")

    return output


def evaluate_probabilities(predictions: pd.DataFrame) -> dict[str, float]:
    season_metrics: list[dict[str, float]] = []

    for _, season_rows in predictions.groupby("season", sort=True):
        ranked = season_rows.sort_values(
            [PROBABILITY_COLUMN, "team_id"],
            ascending=[False, True],
        )
        champion = season_rows[season_rows[TARGET_COLUMN] == 1]
        if len(champion) != 1:
            raise ModelTrainingError("Evaluation requires one champion per season.")

        champion_probability = float(champion.iloc[0][PROBABILITY_COLUMN])
        y = season_rows[TARGET_COLUMN].to_numpy(dtype=float)
        probabilities = season_rows[PROBABILITY_COLUMN].to_numpy(dtype=float)
        champion_team_id = int(champion.iloc[0]["team_id"])
        top_team_ids = ranked["team_id"].astype(int).tolist()

        season_metrics.append(
            {
                "log_loss": -float(np.log(max(champion_probability, 1e-15))),
                "brier_score": float(np.sum((probabilities - y) ** 2)),
                "top_1": float(top_team_ids[0] == champion_team_id),
                "top_3": float(champion_team_id in top_team_ids[:3]),
                "champion_probability": champion_probability,
            }
        )

    metrics = pd.DataFrame(season_metrics).mean().to_dict()
    return {
        "log_loss": float(metrics["log_loss"]),
        "brier_score": float(metrics["brier_score"]),
        "top_1_champion_accuracy": float(metrics["top_1"]),
        "top_3_champion_inclusion_rate": float(metrics["top_3"]),
        "average_champion_probability": float(metrics["champion_probability"]),
    }


def score_model(
    pipeline: Pipeline,
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    scores = pipeline.predict_proba(frame[list(FEATURE_ALLOWLIST)])[:, 1]
    predictions = normalize_season_probabilities(frame, scores)
    return predictions, evaluate_probabilities(predictions)


def score_win_pct_baseline(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    predictions = normalize_season_probabilities(
        frame,
        frame["win_pct"].to_numpy(dtype=float),
        score_column="win_pct_score",
    )
    return predictions, evaluate_probabilities(predictions)


def _season_range(frame: pd.DataFrame) -> dict[str, Any]:
    seasons = sorted(frame["season"].astype(str).unique(), key=season_start_year)
    return {
        "start": seasons[0],
        "end": seasons[-1],
        "count": len(seasons),
        "row_count": len(frame),
    }


def train_baseline(
    historical_path: Path,
    heldout_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    historical, heldout = load_model_data(historical_path, heldout_path)
    train, validation, test = chronological_split(historical, heldout)

    pipeline = build_pipeline()
    pipeline.fit(
        train[list(FEATURE_ALLOWLIST)],
        train[TARGET_COLUMN].astype(int),
    )

    validation_predictions, validation_metrics = score_model(pipeline, validation)
    test_predictions, test_metrics = score_model(pipeline, test)
    _, validation_baseline = score_win_pct_baseline(validation)
    _, test_baseline = score_win_pct_baseline(test)

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "logistic_baseline_pipeline.joblib"
    metadata_path = output_dir / "logistic_baseline_metadata.json"
    validation_path = output_dir / "logistic_baseline_validation_predictions.csv"
    test_path = output_dir / "logistic_baseline_test_predictions.csv"

    joblib.dump(pipeline, model_path)
    validation_predictions.to_csv(validation_path, index=False)
    test_predictions.to_csv(test_path, index=False)

    metadata = {
        "model_version": MODEL_VERSION,
        "model_type": "LogisticRegression",
        "pipeline_steps": ["median_imputation", "standard_scaling", "logistic_regression"],
        "class_weight": "balanced",
        "features": list(FEATURE_ALLOWLIST),
        "excluded_leakage_fields": EXCLUDED_MODEL_FIELDS,
        "training_cutoff": TRAIN_END_SEASON,
        "splits": {
            "training": _season_range(train),
            "validation": _season_range(validation),
            "test": _season_range(test),
        },
        "evaluation_metrics": {
            "validation": validation_metrics,
            "test": test_metrics,
        },
        "win_pct_baseline_metrics": {
            "validation": validation_baseline,
            "test": test_baseline,
        },
        "metric_definition": {
            "log_loss": "Mean negative log probability assigned to the champion across seasons.",
            "brier_score": "Mean per-season sum of squared probability errors across all teams.",
            "top_1_champion_accuracy": "Share of seasons where the highest-probability team was champion.",
            "top_3_champion_inclusion_rate": "Share of seasons where the champion ranked in the top three.",
            "average_champion_probability": "Mean normalized probability assigned to the champion.",
        },
        "probability_normalization": "Scores are nonnegative and normalized to sum to 1.0 within each season.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return {
        "model_path": str(model_path),
        "metadata_path": str(metadata_path),
        "validation_predictions_path": str(validation_path),
        "test_predictions_path": str(test_path),
        **metadata,
    }
