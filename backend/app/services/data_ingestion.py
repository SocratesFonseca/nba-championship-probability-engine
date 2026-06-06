from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings

DATASET_SOURCE_NAME = "Kaggle NBA/ABA/BAA Stats"
DATASET_SOURCE_URL = "https://www.kaggle.com/datasets/sumitrodatta/nba-aba-baa-stats"


@dataclass(frozen=True)
class ExpectedCsvFile:
    filename: str
    required_column_groups: tuple[tuple[str, ...], ...]


EXPECTED_CSV_FILES: tuple[ExpectedCsvFile, ...] = (
    ExpectedCsvFile(
        filename="Player Totals.csv",
        required_column_groups=(
            ("season", "year", "seas_id"),
            ("player", "player_name"),
            ("tm", "team", "team_id"),
        ),
    ),
    ExpectedCsvFile(
        filename="Team Summaries.csv",
        required_column_groups=(
            ("season", "year", "seas_id"),
            ("tm", "team", "team_id", "franch_id"),
        ),
    ),
)


class IngestionError(Exception):
    pass


def get_data_dir(data_dir: str | None = None) -> Path:
    if data_dir:
        return Path(data_dir).expanduser()

    return settings.resolved_nba_data_dir


def _normalize_column(column: str) -> str:
    return column.strip().lower().replace(" ", "_")


def _read_csv_header(path: Path) -> list[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.reader(csv_file)
            return next(reader, [])
    except UnicodeDecodeError:
        with path.open("r", encoding="latin-1", newline="") as csv_file:
            reader = csv.reader(csv_file)
            return next(reader, [])
    except OSError as exc:
        raise IngestionError(f"Could not read {path.name}: {exc}") from exc


def _count_csv_rows(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.reader(csv_file)
            next(reader, None)
            return sum(1 for _ in reader)
    except UnicodeDecodeError:
        with path.open("r", encoding="latin-1", newline="") as csv_file:
            reader = csv.reader(csv_file)
            next(reader, None)
            return sum(1 for _ in reader)
    except OSError as exc:
        raise IngestionError(f"Could not count rows for {path.name}: {exc}") from exc


def validate_expected_files(data_dir: Path) -> dict[str, Any]:
    data_dir = data_dir.resolve()
    discovered_csv_files = sorted(path.name for path in data_dir.glob("*.csv")) if data_dir.exists() else []
    file_results: list[dict[str, Any]] = []

    if not data_dir.exists():
        return {
            "data_dir": str(data_dir),
            "data_dir_exists": False,
            "expected_files": [item.filename for item in EXPECTED_CSV_FILES],
            "present_files": [],
            "missing_files": [item.filename for item in EXPECTED_CSV_FILES],
            "discovered_csv_files": [],
            "files": [],
            "is_valid": False,
            "messages": [f"Data directory does not exist: {data_dir}"],
        }

    messages: list[str] = []

    for expected in EXPECTED_CSV_FILES:
        path = data_dir / expected.filename
        if not path.exists():
            file_results.append(
                {
                    "filename": expected.filename,
                    "exists": False,
                    "valid": False,
                    "missing_column_groups": [],
                    "columns": [],
                    "row_count": 0,
                    "file_size_bytes": 0,
                }
            )
            messages.append(f"Missing expected file: {expected.filename}")
            continue

        columns = _read_csv_header(path)
        normalized_columns = {_normalize_column(column) for column in columns}
        missing_column_groups = [
            list(group)
            for group in expected.required_column_groups
            if not any(_normalize_column(candidate) in normalized_columns for candidate in group)
        ]
        row_count = _count_csv_rows(path)
        valid = not missing_column_groups

        if not valid:
            messages.append(
                f"{expected.filename} is missing required columns: {missing_column_groups}"
            )

        file_results.append(
            {
                "filename": expected.filename,
                "exists": True,
                "valid": valid,
                "missing_column_groups": missing_column_groups,
                "columns": columns,
                "row_count": row_count,
                "file_size_bytes": path.stat().st_size,
            }
        )

    present_files = [item["filename"] for item in file_results if item["exists"]]
    missing_files = [item["filename"] for item in file_results if not item["exists"]]
    is_valid = bool(file_results) and not missing_files and all(item["valid"] for item in file_results)

    if is_valid:
        messages.append("Expected dataset files are present and basic columns look valid.")
    elif discovered_csv_files and not present_files:
        messages.append("CSV files were found, but not the expected Kaggle export filenames.")

    return {
        "data_dir": str(data_dir),
        "data_dir_exists": True,
        "expected_files": [item.filename for item in EXPECTED_CSV_FILES],
        "present_files": present_files,
        "missing_files": missing_files,
        "discovered_csv_files": discovered_csv_files,
        "files": file_results,
        "is_valid": is_valid,
        "messages": messages,
    }


def get_latest_dataset_import(db):
    from sqlalchemy import select

    from app.models.dataset_import import DatasetImport

    return db.scalars(
        select(DatasetImport).order_by(DatasetImport.imported_at.desc())
    ).first()


def get_data_status(db, data_dir: str | None = None) -> dict[str, Any]:
    resolved_data_dir = get_data_dir(data_dir)
    validation = validate_expected_files(resolved_data_dir)
    latest_import = get_latest_dataset_import(db)

    imported = latest_import is not None and latest_import.status == "imported"
    next_steps: list[str] = []

    if not validation["data_dir_exists"]:
        next_steps.append("Create the data directory or set NBA_DATA_DIR to the directory containing the Kaggle CSV files.")
    elif validation["missing_files"]:
        next_steps.append("Download the Kaggle dataset and place the expected CSV files in the data directory.")
    elif not validation["is_valid"]:
        next_steps.append("Check the CSV headers against the expected Kaggle file format.")
    elif not imported:
        next_steps.append("Run the ingestion command to store dataset metadata in the database.")
    else:
        next_steps.append("Dataset metadata is imported. The next milestone is raw stats table design and loading.")

    return {
        "source_name": DATASET_SOURCE_NAME,
        "source_url": DATASET_SOURCE_URL,
        "data_dir": validation["data_dir"],
        "data_dir_configured": settings.is_data_dir_configured if data_dir is None else True,
        "data_dir_exists": validation["data_dir_exists"],
        "expected_files": validation["expected_files"],
        "present_files": validation["present_files"],
        "missing_files": validation["missing_files"],
        "discovered_csv_files": validation["discovered_csv_files"],
        "files_valid": validation["is_valid"],
        "database_has_import_metadata": imported,
        "last_imported_at": latest_import.imported_at.isoformat() if latest_import else None,
        "messages": validation["messages"] + next_steps,
    }


def import_dataset_metadata(data_dir: str | None = None) -> dict[str, Any]:
    resolved_data_dir = get_data_dir(data_dir)
    validation = validate_expected_files(resolved_data_dir)

    if not validation["is_valid"]:
        raise IngestionError("; ".join(validation["messages"]) or "Dataset validation failed.")

    from app.core.database import Base, SessionLocal, engine
    from app.models.dataset_import import DatasetFileMetadata, DatasetImport

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        dataset_import = DatasetImport(
            source_name=DATASET_SOURCE_NAME,
            source_url=DATASET_SOURCE_URL,
            data_dir=validation["data_dir"],
            status="imported",
            expected_files_count=len(validation["expected_files"]),
            present_files_count=len(validation["present_files"]),
            missing_files_json=json.dumps(validation["missing_files"]),
        )
        db.add(dataset_import)
        db.flush()

        for file_result in validation["files"]:
            db.add(
                DatasetFileMetadata(
                    import_id=dataset_import.id,
                    filename=file_result["filename"],
                    row_count=file_result["row_count"],
                    column_count=len(file_result["columns"]),
                    file_size_bytes=file_result["file_size_bytes"],
                    columns_json=json.dumps(file_result["columns"]),
                )
            )

        db.commit()
        db.refresh(dataset_import)

        return {
            "status": dataset_import.status,
            "import_id": dataset_import.id,
            "imported_at": dataset_import.imported_at.isoformat(),
            "files_imported": len(validation["present_files"]),
            "data_dir": validation["data_dir"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Kaggle NBA dataset metadata.")
    parser.add_argument("--data-dir", default=None, help="Directory containing the Kaggle CSV files.")
    args = parser.parse_args()

    try:
        result = import_dataset_metadata(args.data_dir)
    except IngestionError as exc:
        print(f"Ingestion failed: {exc}")
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())