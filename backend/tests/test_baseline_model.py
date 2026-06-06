import numpy as np
import pandas as pd
import pytest

from app.services.baseline_model import (
    FEATURE_ALLOWLIST,
    ModelTrainingError,
    chronological_split,
    normalize_season_probabilities,
    validate_feature_allowlist,
)


def make_rows(start_year, end_year):
    rows = []
    for year in range(start_year, end_year + 1):
        season = f"{year}-{str(year + 1)[-2:]}"
        for team_id in (1, 2):
            row = {
                "season": season,
                "team_id": team_id,
                "team_name": f"Team {team_id}",
                "champion": int(team_id == 1),
            }
            row.update({feature: float(team_id) for feature in FEATURE_ALLOWLIST})
            rows.append(row)
    return pd.DataFrame(rows)


def test_chronological_split_keeps_seasons_together():
    historical = make_rows(1984, 2010)
    heldout = make_rows(2011, 2012)

    train, validation, test = chronological_split(historical, heldout)

    assert train["season"].min() == "1984-85"
    assert train["season"].max() == "2006-07"
    assert validation["season"].min() == "2007-08"
    assert validation["season"].max() == "2010-11"
    assert test["season"].min() == "2011-12"
    assert set(train["season"]).isdisjoint(validation["season"])
    assert set(validation["season"]).isdisjoint(test["season"])


def test_feature_allowlist_rejects_leakage():
    with pytest.raises(ModelTrainingError, match="Leakage-prone"):
        validate_feature_allowlist(
            [*FEATURE_ALLOWLIST, "champion"],
            (*FEATURE_ALLOWLIST, "champion"),
        )


def test_probabilities_sum_to_one_within_each_season():
    frame = make_rows(2011, 2012)
    scores = np.array([0.2, 0.8, 0.7, 0.3])

    predictions = normalize_season_probabilities(frame, scores)
    sums = predictions.groupby("season")["championship_probability"].sum()

    assert np.allclose(sums.to_numpy(), 1.0)
    assert (predictions["championship_probability"] >= 0).all()
