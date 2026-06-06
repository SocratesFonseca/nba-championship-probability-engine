import csv

import pytest

from app.core.database import SessionLocal
from app.models.dataset_import import DatasetFileMetadata, DatasetImport
from app.services.data_ingestion import IngestionError, import_dataset_metadata


def write_csv(path, columns):
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(columns)
        writer.writerow(["2024"] * len(columns))


def test_import_dataset_metadata_records_real_file_metadata(tmp_path):
    write_csv(tmp_path / "Player Totals.csv", ["season", "player", "tm"])
    write_csv(tmp_path / "Team Summaries.csv", ["season", "tm"])

    result = import_dataset_metadata(str(tmp_path))

    assert result["status"] == "imported"
    assert result["files_imported"] == 2

    with SessionLocal() as db:
        assert db.query(DatasetImport).count() == 1
        assert db.query(DatasetFileMetadata).count() == 2


def test_import_dataset_metadata_rejects_missing_columns(tmp_path):
    write_csv(tmp_path / "Player Totals.csv", ["season", "player"])
    write_csv(tmp_path / "Team Summaries.csv", ["season", "tm"])

    with pytest.raises(IngestionError, match="missing required columns"):
        import_dataset_metadata(str(tmp_path))
