from app.core.config import Settings


def test_sqlite_is_the_default_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.resolved_database_url == "sqlite:///nba_local.db"


def test_railway_postgres_url_is_normalized():
    settings = Settings(
        database_url="postgres://user:password@postgres.example.com:5432/nba",
        _env_file=None,
    )

    assert settings.resolved_database_url.startswith("postgresql://")
