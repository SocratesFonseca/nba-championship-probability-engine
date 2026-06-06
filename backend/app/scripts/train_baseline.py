from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import settings
from app.services.baseline_model import ModelTrainingError, train_baseline


def main() -> int:
    processed_dir = settings.resolved_nba_processed_dir
    parser = argparse.ArgumentParser(
        description="Train and evaluate the logistic regression baseline."
    )
    parser.add_argument(
        "--historical-data",
        default=str(processed_dir / "team_season_training.csv"),
    )
    parser.add_argument(
        "--heldout-data",
        default=str(processed_dir / "heldout" / "team_season_training.csv"),
    )
    parser.add_argument(
        "--output-dir",
        default=str(settings.resolved_nba_model_output_dir),
    )
    args = parser.parse_args()

    try:
        result = train_baseline(
            historical_path=Path(args.historical_data),
            heldout_path=Path(args.heldout_data),
            output_dir=Path(args.output_dir),
        )
    except ModelTrainingError as exc:
        print(f"Training failed: {exc}")
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
