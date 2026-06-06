import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from app.services.baseline_model import FEATURE_ALLOWLIST, build_pipeline
from app.services.prediction_service import (
    METADATA_FILENAME,
    MODEL_FILENAME,
    clear_prediction_caches,
)
TEST_ROOT = Path(__file__).resolve().parent
TEST_OUTPUT_DIR = TEST_ROOT / "test_outputs"
TEST_PROCESSED_DIR = TEST_ROOT / "test_processed"


def make_season(season, champion_team_id):
    rows = []
    for team_id, win_pct in ((1, 0.75), (2, 0.6), (3, 0.45)):
        row = {
            "season": season,
            "team_id": team_id,
            "team_name": f"Team {team_id}",
            "champion": int(team_id == champion_team_id),
            "gp": 82,
            "wins": round(win_pct * 82),
            "losses": 82 - round(win_pct * 82),
            "win_pct": win_pct,
            "fgm_per_game": 42.0 - team_id,
            "fga_per_game": 88.0,
            "fg_pct": 0.49 - team_id * 0.01,
            "ftm_per_game": 18.0,
            "fta_per_game": 23.0,
            "ft_pct": 0.78,
            "pts_per_game": 116.0 - team_id,
        }
        rows.append(row)
    return rows


@pytest.fixture(autouse=True)
def prediction_artifacts():
    shutil.rmtree(TEST_OUTPUT_DIR, ignore_errors=True)
    shutil.rmtree(TEST_PROCESSED_DIR, ignore_errors=True)
    TEST_OUTPUT_DIR.mkdir(parents=True)
    (TEST_PROCESSED_DIR / "heldout").mkdir(parents=True)

    historical = pd.DataFrame(
        make_season("2006-07", 1) + make_season("2007-08", 2)
    )
    heldout = pd.DataFrame(
        make_season("2011-12", 2) + make_season("2012-13", 1)
    )
    historical.to_csv(
        TEST_PROCESSED_DIR / "team_season_training.csv",
        index=False,
    )
    heldout.to_csv(
        TEST_PROCESSED_DIR / "heldout" / "team_season_training.csv",
        index=False,
    )

    training_rows = pd.concat(
        [historical, pd.DataFrame(make_season("2005-06", 1))],
        ignore_index=True,
    )
    pipeline = build_pipeline()
    pipeline.fit(
        training_rows[list(FEATURE_ALLOWLIST)],
        training_rows["champion"],
    )
    joblib.dump(pipeline, TEST_OUTPUT_DIR / MODEL_FILENAME)
    metadata = {
        "model_version": "test-model-v1",
        "model_type": "LogisticRegression",
        "training_cutoff": "2006-07",
        "features": list(FEATURE_ALLOWLIST),
        "evaluation_metrics": {"validation": {}, "test": {}},
        "generated_at": "2026-06-06T00:00:00+00:00",
        "splits": {
            "validation": {"start": "2007-08", "end": "2010-11"},
            "test": {"start": "2011-12", "end": "2012-13"},
        },
    }
    (TEST_OUTPUT_DIR / METADATA_FILENAME).write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    clear_prediction_caches()

    yield

    clear_prediction_caches()
    shutil.rmtree(TEST_OUTPUT_DIR, ignore_errors=True)
    shutil.rmtree(TEST_PROCESSED_DIR, ignore_errors=True)


def test_model_status(client):
    response = client.get("/models/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["model_version"] == "test-model-v1"
    assert payload["features"] == list(FEATURE_ALLOWLIST)
    assert "path" not in json.dumps(payload).lower()


def test_historical_prediction_probability_and_ranking(client):
    response = client.get("/predictions/2011-12")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_type"] == "historical holdout prediction"
    assert len(payload["teams"]) == 3
    assert sum(team["actual_champion"] for team in payload["teams"]) == 1
    probabilities = [team["championship_probability"] for team in payload["teams"]]
    assert np.isclose(sum(probabilities), 1.0)
    assert probabilities == sorted(probabilities, reverse=True)
    assert [team["rank"] for team in payload["teams"]] == [1, 2, 3]
    assert len({team["team_id"] for team in payload["teams"]}) == 3


def test_latest_available_season(client):
    response = client.get("/predictions/latest")

    assert response.status_code == 200
    assert response.json()["season"] == "2012-13"


def test_missing_and_malformed_seasons(client):
    assert client.get("/predictions/1999-00").status_code == 404
    assert client.get("/predictions/2023").status_code == 422
    assert client.get("/predictions/2023-99").status_code == 422


def test_missing_model_status_and_prediction(client):
    model_path = TEST_OUTPUT_DIR / MODEL_FILENAME
    backup_path = TEST_OUTPUT_DIR / f"{MODEL_FILENAME}.bak"
    model_path.rename(backup_path)
    clear_prediction_caches()

    status_response = client.get("/models/status")
    prediction_response = client.get("/predictions/2011-12")

    assert status_response.status_code == 200
    assert status_response.json()["available"] is False
    assert prediction_response.status_code == 503
    assert "path" not in prediction_response.text.lower()


def test_incompatible_features_return_503(client):
    heldout_path = TEST_PROCESSED_DIR / "heldout" / "team_season_training.csv"
    frame = pd.read_csv(heldout_path).drop(columns=[FEATURE_ALLOWLIST[-1]])
    frame.to_csv(heldout_path, index=False)
    clear_prediction_caches()

    response = client.get("/predictions/2011-12")

    assert response.status_code == 503
    assert "incompatible" in response.json()["detail"].lower()


def test_metadata_leakage_feature_returns_503(client):
    metadata_path = TEST_OUTPUT_DIR / METADATA_FILENAME
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["features"].append("champion")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    clear_prediction_caches()

    response = client.get("/predictions/2011-12")

    assert response.status_code == 503
    assert "leakage" in response.json()["detail"].lower()
