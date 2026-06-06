import json

import pytest

from app.services.nba_data_collection import (
    CollectionError,
    CollectionOptions,
    FEATURE_COLUMNS,
    NbaApiClient,
    TARGET_COLUMN,
    collect_training_dataset,
    identify_champion,
    validate_training_rows,
)


def payload(rows):
    headers = list(rows[0]) if rows else []
    return {
        "resultSets": [
            {
                "name": "LeagueDashTeamStats",
                "headers": headers,
                "rowSet": [[row[column] for column in headers] for row in rows],
            }
        ]
    }


def regular_game(team_id, team_name, game_id, result, points):
    return {
        "TEAM_ID": team_id,
        "TEAM_NAME": team_name,
        "GAME_ID": game_id,
        "WL": result,
        "FGM": 40,
        "FGA": 84,
        "FG3M": 12,
        "FG3A": 32,
        "FTM": 20,
        "FTA": 25,
        "OREB": 10,
        "DREB": 34,
        "REB": 44,
        "AST": 26,
        "TOV": 13,
        "STL": 7,
        "BLK": 5,
        "PF": 19,
        "PTS": points,
    }


class FakeClient:
    def __init__(self):
        self.calls = []

    def fetch_regular_games(self, season):
        self.calls.append((season, "Regular Season Game Log"))
        return payload(
            [
                regular_game(1, "Team One", "1", "W", 115),
                regular_game(2, "Team Two", "1", "L", 108),
                regular_game(1, "Team One", "2", "L", 101),
                regular_game(2, "Team Two", "2", "W", 109),
                regular_game(1, "Team One", "3", "", 0),
            ]
        )

    def fetch_playoff_games(self, season):
        self.calls.append((season, "Playoff Game Log"))
        return payload(
            [
                {
                    "TEAM_ID": 1,
                    "GAME_ID": "0042300405",
                    "GAME_DATE": "JUN 17, 2024",
                    "WL": "W",
                },
                {
                    "TEAM_ID": 2,
                    "GAME_ID": "0042300405",
                    "GAME_DATE": "JUN 17, 2024",
                    "WL": "L",
                },
            ]
        )


def test_collection_builds_valid_dataset_and_resumes_from_cache(tmp_path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    options = CollectionOptions(
        start_season="2023-24",
        end_season="2023-24",
        raw_dir=raw_dir,
        processed_dir=processed_dir,
    )
    client = FakeClient()

    result = collect_training_dataset(options, client=client)

    assert result["row_count"] == 2
    assert len(client.calls) == 2
    assert TARGET_COLUMN not in FEATURE_COLUMNS
    training_text = (processed_dir / "team_season_training.csv").read_text(
        encoding="utf-8"
    )
    assert "Team One" in training_text
    assert "Team Two" in training_text
    metadata = json.loads(
        (processed_dir / "team_season_training_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    assert metadata["validation_results"]["one_champion_per_season"] is True

    resumed_client = FakeClient()
    resumed = collect_training_dataset(options, client=resumed_client)
    assert resumed["cache_hits"] == 2
    assert resumed_client.calls == []


def test_api_client_retries_without_live_network(monkeypatch):
    client = NbaApiClient(
        request_delay_seconds=0,
        max_retries=3,
        sleep=lambda _: None,
    )
    attempts = {"count": 0}

    def fake_request(season, season_type):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise TimeoutError("timed out")
        return {"resultSets": []}

    monkeypatch.setattr(client, "_request_game_log", fake_request)

    assert client.fetch_regular_games("2023-24") == {
        "resultSets": []
    }
    assert attempts["count"] == 3


def test_champion_identification_rejects_ambiguous_final():
    with pytest.raises(CollectionError, match="one winner"):
        identify_champion(
            [
                {
                    "TEAM_ID": 1,
                    "GAME_ID": "1",
                    "GAME_DATE": "JUN 17, 2024",
                    "WL": "W",
                },
                {
                    "TEAM_ID": 2,
                    "GAME_ID": "1",
                    "GAME_DATE": "JUN 17, 2024",
                    "WL": "W",
                },
            ],
            "2023-24",
        )


def test_validation_rejects_duplicate_team_seasons():
    row = {
        "season": "2023-24",
        "team_id": 1,
        "team_name": "Team One",
        "gp": 82,
        "wins": 52,
        "losses": 30,
        "win_pct": 0.634,
        "fg_pct": 0.48,
        "fgm_per_game": 40.0,
        "fga_per_game": 84.0,
        "ftm_per_game": 20.0,
        "fta_per_game": 25.0,
        "ft_pct": 0.79,
        "pts_per_game": 115.0,
        "champion": 1,
    }

    with pytest.raises(CollectionError, match="Duplicate team-season"):
        validate_training_rows([row, row.copy()])
