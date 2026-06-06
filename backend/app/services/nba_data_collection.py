from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.core.config import settings

SOURCE_NAME = "NBA.com Stats API through nba_api"
TRAINING_FILENAME = "team_season_training.csv"
METADATA_FILENAME = "team_season_training_metadata.json"
DEFAULT_TRAINING_START_SEASON = "1984-85"
DEFAULT_TRAINING_END_SEASON = "2010-11"
TARGET_COLUMN = "champion"
IDENTIFIER_COLUMNS = ["season", "team_id", "team_name"]
FEATURE_COLUMNS = [
    "gp",
    "wins",
    "losses",
    "win_pct",
    "fgm_per_game",
    "fga_per_game",
    "fg_pct",
    "ftm_per_game",
    "fta_per_game",
    "ft_pct",
    "pts_per_game",
]
EXCLUDED_LEAKAGE_COLUMNS = [
    "playoff_games",
    "playoff_wins",
    "playoff_losses",
    "playoff_results",
    "finals_results",
    "championship_indicators",
    "postseason_statistics",
]
EXCLUDED_INCOMPLETE_HISTORICAL_COLUMNS = [
    "fg3m",
    "fg3a",
    "fg3_pct",
    "oreb",
    "dreb",
    "reb",
    "ast",
    "tov",
    "stl",
    "blk",
    "pf",
    "plus_minus",
]

REGULAR_GAME_COLUMNS = (
    "TEAM_ID",
    "TEAM_NAME",
    "GAME_ID",
    "WL",
    "FGM",
    "FGA",
    "FTM",
    "FTA",
    "PTS",
)


class CollectionError(Exception):
    pass


@dataclass(frozen=True)
class CollectionOptions:
    start_season: str
    end_season: str
    raw_dir: Path
    processed_dir: Path
    refresh: bool = False


def parse_season(season: str) -> tuple[int, int]:
    try:
        start_text, end_text = season.split("-", 1)
        start_year = int(start_text)
        end_year = int(f"{start_text[:2]}{end_text}")
    except (TypeError, ValueError):
        raise CollectionError(
            f"Invalid season '{season}'. Use NBA format such as 2023-24."
        ) from None

    if end_year != start_year + 1:
        raise CollectionError(
            f"Invalid season '{season}'. The end year must follow the start year."
        )

    return start_year, end_year


def latest_completed_season(today: date | None = None) -> str:
    today = today or date.today()
    end_year = today.year if today.month >= 8 else today.year - 1
    start_year = end_year - 1
    return f"{start_year}-{str(end_year)[-2:]}"


def season_range(start_season: str, end_season: str) -> list[str]:
    start_year, _ = parse_season(start_season)
    end_start_year, end_year = parse_season(end_season)
    _, latest_end_year = parse_season(latest_completed_season())

    if start_year > end_start_year:
        raise CollectionError("Start season must not be after end season.")
    if end_year > latest_end_year:
        raise CollectionError(
            f"{end_season} is not a completed season. Latest allowed: "
            f"{latest_completed_season()}."
        )

    return [
        f"{year}-{str(year + 1)[-2:]}"
        for year in range(start_year, end_start_year + 1)
    ]


def _result_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result_sets = payload.get("resultSets") or payload.get("resultSet")
    if isinstance(result_sets, dict):
        result_sets = [result_sets]
    if not isinstance(result_sets, list) or not result_sets:
        raise CollectionError("NBA API response did not contain a result set.")

    result_set = result_sets[0]
    headers = result_set.get("headers")
    rows = result_set.get("rowSet")
    if not isinstance(headers, list) or not isinstance(rows, list):
        raise CollectionError("NBA API result set is missing headers or rows.")

    return [dict(zip(headers, row, strict=False)) for row in rows]


class NbaApiClient:
    def __init__(
        self,
        *,
        timeout_seconds: int | None = None,
        request_delay_seconds: float | None = None,
        max_retries: int | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.timeout_seconds = timeout_seconds or settings.nba_api_timeout_seconds
        self.request_delay_seconds = (
            settings.nba_api_request_delay_seconds
            if request_delay_seconds is None
            else request_delay_seconds
        )
        self.max_retries = max_retries or settings.nba_api_max_retries
        self.sleep = sleep

    def _request_game_log(self, season: str, season_type: str) -> dict[str, Any]:
        from nba_api.stats.endpoints import leaguegamelog

        endpoint = leaguegamelog.LeagueGameLog(
            counter=0,
            direction="ASC",
            league_id="00",
            player_or_team_abbreviation="T",
            season=season,
            season_type_all_star=season_type,
            sorter="DATE",
            timeout=self.timeout_seconds,
        )
        return endpoint.get_dict()

    def _request_playoff_games(self, season: str) -> dict[str, Any]:
        return self._request_game_log(season, "Playoffs")

    def _with_retries(
        self,
        request: Callable[[], dict[str, Any]],
        description: str,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            if self.request_delay_seconds > 0:
                self.sleep(self.request_delay_seconds)

            try:
                return request()
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    self.sleep(self.request_delay_seconds * attempt)

        raise CollectionError(
            f"NBA.com request failed for {description} after "
            f"{self.max_retries} attempts: {last_error}"
        )

    def fetch_regular_games(self, season: str) -> dict[str, Any]:
        return self._with_retries(
            lambda: self._request_game_log(season, "Regular Season"),
            f"{season} regular-season game log",
        )

    def fetch_playoff_games(self, season: str) -> dict[str, Any]:
        return self._with_retries(
            lambda: self._request_playoff_games(season),
            f"{season} playoff game log",
        )


def load_or_fetch_regular_games(
    client: NbaApiClient,
    *,
    season: str,
    raw_dir: Path,
    refresh: bool,
) -> tuple[dict[str, Any], Path, bool]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache_path = raw_dir / f"{season}_regular_season_game_log.json"

    if cache_path.exists() and not refresh:
        try:
            return json.loads(cache_path.read_text(encoding="utf-8")), cache_path, True
        except (OSError, json.JSONDecodeError) as exc:
            raise CollectionError(f"Could not read cache file {cache_path}: {exc}") from exc

    payload = client.fetch_regular_games(season)
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload, cache_path, False


def load_or_fetch_playoff_games(
    client: NbaApiClient,
    *,
    season: str,
    raw_dir: Path,
    refresh: bool,
) -> tuple[dict[str, Any], Path, bool]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache_path = raw_dir / f"{season}_playoff_game_log.json"

    if cache_path.exists() and not refresh:
        try:
            return json.loads(cache_path.read_text(encoding="utf-8")), cache_path, True
        except (OSError, json.JSONDecodeError) as exc:
            raise CollectionError(f"Could not read cache file {cache_path}: {exc}") from exc

    payload = client.fetch_playoff_games(season)
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload, cache_path, False


def _parse_game_date(value: Any, season: str) -> datetime:
    text = str(value).strip()
    for date_format in ("%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue
    raise CollectionError(f"Unrecognized playoff game date '{text}' for {season}.")


def identify_champion(playoff_rows: list[dict[str, Any]], season: str) -> int:
    if not playoff_rows:
        raise CollectionError(f"No playoff game data was returned for {season}.")

    dated_rows: list[tuple[datetime, dict[str, Any]]] = []
    required_columns = ("TEAM_ID", "GAME_ID", "GAME_DATE", "WL")
    for row in playoff_rows:
        if not all(column in row for column in required_columns):
            raise CollectionError(
                f"Playoff game response for {season} is missing required columns."
            )
        dated_rows.append((_parse_game_date(row["GAME_DATE"], season), row))

    final_date = max(game_date for game_date, _ in dated_rows)
    final_rows = [row for game_date, row in dated_rows if game_date == final_date]
    final_game_ids = {str(row["GAME_ID"]) for row in final_rows}
    if len(final_game_ids) != 1:
        raise CollectionError(
            f"Could not identify one final playoff game for {season}."
        )

    winners = [row for row in final_rows if str(row["WL"]).upper() == "W"]
    if len(winners) != 1:
        raise CollectionError(
            f"Could not identify one winner of the final playoff game for {season}."
        )

    return int(winners[0]["TEAM_ID"])


def build_team_season_rows(
    season: str,
    regular_game_rows: list[dict[str, Any]],
    champion_team_id: int,
) -> list[dict[str, Any]]:
    if not regular_game_rows:
        raise CollectionError(f"No regular-season game data was returned for {season}.")

    teams: dict[int, dict[str, Any]] = {}
    seen_team_games: set[tuple[int, str]] = set()

    for source_row in regular_game_rows:
        missing = [column for column in REGULAR_GAME_COLUMNS if column not in source_row]
        if missing:
            raise CollectionError(
                f"Regular-season game log for {season} is missing columns: "
                f"{', '.join(missing)}"
            )

        result = str(source_row["WL"] or "").upper()
        if not result and float(source_row["PTS"] or 0) == 0:
            continue

        try:
            team_id = int(source_row["TEAM_ID"])
            game_id = str(source_row["GAME_ID"])
        except (TypeError, ValueError):
            raise CollectionError(
                f"Regular-season game log for {season} has an invalid team or game ID."
            ) from None

        team_game_key = (team_id, game_id)
        if team_game_key in seen_team_games:
            raise CollectionError(
                f"Duplicate team-game row found for {season}, team {team_id}."
            )
        seen_team_games.add(team_game_key)

        team = teams.setdefault(
            team_id,
            {
                "team_name": str(source_row["TEAM_NAME"]).strip(),
                "gp": 0,
                "wins": 0,
                "losses": 0,
                "FGM": 0.0,
                "FGA": 0.0,
                "FTM": 0.0,
                "FTA": 0.0,
                "PTS": 0.0,
            },
        )
        team["gp"] += 1
        if result == "W":
            team["wins"] += 1
        elif result == "L":
            team["losses"] += 1
        else:
            raise CollectionError(
                f"Regular-season game log for {season} has an invalid WL value."
            )

        for column in (
            "FGM",
            "FGA",
            "FTM",
            "FTA",
            "PTS",
        ):
            try:
                team[column] += float(source_row[column])
            except (TypeError, ValueError):
                raise CollectionError(
                    f"Regular-season game log for {season} has an invalid {column} value."
                ) from None

    output: list[dict[str, Any]] = []
    for team_id, totals in sorted(teams.items()):
        gp = int(totals["gp"])
        row = {
            "season": season,
            "team_id": team_id,
            "team_name": totals["team_name"],
            "gp": gp,
            "wins": int(totals["wins"]),
            "losses": int(totals["losses"]),
            "win_pct": totals["wins"] / gp,
            "fgm_per_game": totals["FGM"] / gp,
            "fga_per_game": totals["FGA"] / gp,
            "fg_pct": totals["FGM"] / totals["FGA"] if totals["FGA"] else 0.0,
            "ftm_per_game": totals["FTM"] / gp,
            "fta_per_game": totals["FTA"] / gp,
            "ft_pct": totals["FTM"] / totals["FTA"] if totals["FTA"] else 0.0,
            "pts_per_game": totals["PTS"] / gp,
            TARGET_COLUMN: int(team_id == champion_team_id),
        }
        output.append(row)

    return output


def validate_training_rows(rows: list[dict[str, Any]]) -> dict[str, bool]:
    if not rows:
        raise CollectionError("Training dataset has no rows.")

    keys = [(row.get("season"), row.get("team_id")) for row in rows]
    if len(keys) != len(set(keys)):
        raise CollectionError("Duplicate team-season rows were found.")

    if any(not row.get("season") or not row.get("team_id") or not row.get("team_name") for row in rows):
        raise CollectionError("Missing season, team ID, or team name.")

    champions_by_season: dict[str, int] = {}
    for row in rows:
        season = str(row["season"])
        champions_by_season[season] = champions_by_season.get(season, 0) + int(
            row[TARGET_COLUMN]
        )
    invalid_seasons = [
        season for season, count in champions_by_season.items() if count != 1
    ]
    if invalid_seasons:
        raise CollectionError(
            "Expected exactly one champion in seasons: " + ", ".join(invalid_seasons)
        )

    for row in rows:
        if not 1 <= int(row["gp"]) <= 100:
            raise CollectionError(f"Unreasonable GP value for {row['season']}.")
        if not 0 <= int(row["wins"]) <= int(row["gp"]):
            raise CollectionError(f"Unreasonable wins value for {row['season']}.")
        if not 0 <= int(row["losses"]) <= int(row["gp"]):
            raise CollectionError(f"Unreasonable losses value for {row['season']}.")
        for column in ("win_pct", "fg_pct", "ft_pct"):
            if not 0 <= float(row[column]) <= 1:
                raise CollectionError(
                    f"Unreasonable {column} value for {row['season']}."
                )
        if not 0 <= float(row["pts_per_game"]) <= 200:
            raise CollectionError(f"Unreasonable points value for {row['season']}.")
        for column in ("fgm_per_game", "fga_per_game", "ftm_per_game", "fta_per_game"):
            if not 0 <= float(row[column]) <= 200:
                raise CollectionError(
                    f"Unreasonable {column} value for {row['season']}."
                )

    if TARGET_COLUMN in FEATURE_COLUMNS:
        raise CollectionError("Champion target must not appear in feature columns.")

    return {
        "no_duplicate_team_seasons": True,
        "identifiers_complete": True,
        "one_champion_per_season": True,
        "numeric_ranges_valid": True,
        "target_excluded_from_features": True,
    }


def write_training_dataset(
    rows: list[dict[str, Any]],
    processed_dir: Path,
    *,
    source_files: list[str],
    validations: dict[str, bool],
) -> tuple[Path, Path]:
    processed_dir.mkdir(parents=True, exist_ok=True)
    training_path = processed_dir / TRAINING_FILENAME
    metadata_path = processed_dir / METADATA_FILENAME
    fieldnames = IDENTIFIER_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN]

    with training_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    seasons = sorted({str(row["season"]) for row in rows})
    metadata = {
        "source": SOURCE_NAME,
        "source_files": source_files,
        "row_count": len(rows),
        "season_range": {"start": seasons[0], "end": seasons[-1]},
        "feature_columns": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "excluded_leakage_columns": EXCLUDED_LEAKAGE_COLUMNS,
        "excluded_incomplete_historical_columns": EXCLUDED_INCOMPLETE_HISTORICAL_COLUMNS,
        "league_scope": "NBA only (League ID 00); ABA and BAA are not exposed by this workflow.",
        "default_split_policy": "1984-85 through 2010-11 for training; 2011-12 and later reserved for future evaluation.",
        "champion_method": "Winner of the season's final game in the separate playoff game log response.",
        "unplayed_game_policy": "Rows with a blank WL value and zero points are excluded as unplayed or canceled games.",
        "validation_results": validations,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return training_path, metadata_path


def collect_training_dataset(
    options: CollectionOptions,
    *,
    client: NbaApiClient | None = None,
) -> dict[str, Any]:
    seasons = season_range(options.start_season, options.end_season)
    client = client or NbaApiClient()
    all_rows: list[dict[str, Any]] = []
    source_files: list[str] = []
    cache_hits = 0

    for season in seasons:
        regular_payload, regular_path, regular_cached = load_or_fetch_regular_games(
            client,
            season=season,
            raw_dir=options.raw_dir,
            refresh=options.refresh,
        )
        playoff_payload, playoff_path, playoff_cached = load_or_fetch_playoff_games(
            client,
            season=season,
            raw_dir=options.raw_dir,
            refresh=options.refresh,
        )
        source_files.extend([regular_path.name, playoff_path.name])
        cache_hits += int(regular_cached) + int(playoff_cached)

        regular_game_rows = _result_rows(regular_payload)
        playoff_game_rows = _result_rows(playoff_payload)
        champion_team_id = identify_champion(playoff_game_rows, season)
        all_rows.extend(
            build_team_season_rows(season, regular_game_rows, champion_team_id)
        )

    validations = validate_training_rows(all_rows)
    training_path, metadata_path = write_training_dataset(
        all_rows,
        options.processed_dir,
        source_files=source_files,
        validations=validations,
    )

    return {
        "training_path": str(training_path),
        "metadata_path": str(metadata_path),
        "seasons": seasons,
        "row_count": len(all_rows),
        "feature_columns": FEATURE_COLUMNS,
        "cache_hits": cache_hits,
        "validation_results": validations,
    }


def get_training_data_status() -> dict[str, Any]:
    raw_dir = settings.resolved_nba_api_raw_dir
    processed_dir = settings.resolved_nba_processed_dir
    training_path = processed_dir / TRAINING_FILENAME
    metadata_path = processed_dir / METADATA_FILENAME
    raw_files = sorted(raw_dir.glob("*_game_log.json")) if raw_dir.exists() else []
    metadata: dict[str, Any] | None = None
    messages: list[str] = []

    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            messages.append("Training metadata exists but could not be read.")

    if training_path.exists() and metadata:
        messages.append("Validated training dataset is available.")
    elif raw_files:
        messages.append(
            "Raw NBA API cache exists. Run the collection command to finish the dataset."
        )
    else:
        messages.append(
            "Run python -m app.scripts.collect_nba_data to collect NBA data."
        )

    return {
        "source_name": SOURCE_NAME,
        "workflow": "nba_api",
        "raw_data_dir": str(raw_dir),
        "processed_data_dir": str(processed_dir),
        "raw_cache_files": len(raw_files),
        "training_dataset_available": training_path.exists(),
        "metadata_available": metadata is not None,
        "row_count": metadata.get("row_count") if metadata else None,
        "season_range": metadata.get("season_range") if metadata else None,
        "last_generated_at": metadata.get("generated_at") if metadata else None,
        "validation_results": (
            metadata.get("validation_results") if metadata else None
        ),
        "messages": messages,
    }
