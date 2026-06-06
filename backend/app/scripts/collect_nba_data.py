from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import settings
from app.services.nba_data_collection import (
    CollectionError,
    CollectionOptions,
    DEFAULT_TRAINING_END_SEASON,
    DEFAULT_TRAINING_START_SEASON,
    collect_training_dataset,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect NBA team-season data and build a training dataset."
    )
    parser.add_argument("--start-season", default=DEFAULT_TRAINING_START_SEASON)
    parser.add_argument("--end-season", default=DEFAULT_TRAINING_END_SEASON)
    parser.add_argument(
        "--raw-dir",
        default=str(settings.resolved_nba_api_raw_dir),
        help="Directory for cached raw NBA API responses.",
    )
    parser.add_argument(
        "--processed-dir",
        default=str(settings.resolved_nba_processed_dir),
        help="Directory for the processed CSV and metadata JSON.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore cached responses and request every season again.",
    )
    args = parser.parse_args()

    options = CollectionOptions(
        start_season=args.start_season,
        end_season=args.end_season,
        raw_dir=Path(args.raw_dir),
        processed_dir=Path(args.processed_dir),
        refresh=args.refresh,
    )

    try:
        result = collect_training_dataset(options)
    except CollectionError as exc:
        print(f"Collection failed: {exc}")
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
