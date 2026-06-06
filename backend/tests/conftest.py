import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

TEST_DATABASE_PATH = Path(__file__).resolve().parent / "test_nba.db"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["NBA_DATA_DIR"] = str(DEFAULT_DATA_DIR)
os.environ["ENVIRONMENT"] = "test"

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.dataset_import import DatasetFileMetadata, DatasetImport


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.execute(delete(DatasetFileMetadata))
        db.execute(delete(DatasetImport))
        db.commit()

    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    TEST_DATABASE_PATH.unlink(missing_ok=True)
