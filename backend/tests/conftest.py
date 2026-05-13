"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_settings


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Explicit opt-in: override DATABASE_URL to a temp SQLite file per-test.

    Tests that exercise storage CRUD should depend on this fixture so the DB
    file lifetime matches the test.
    """
    db_path = tmp_path / "test_jobs.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield db_path
    get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _quiet_env(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default to a non-configured environment unless a test overrides.

    Also points DATABASE_URL at a per-test tmp file so that tests which trigger
    `init_db()` (e.g. anything using TestClient + lifespan) don't pollute the
    repo working directory with a real `jobs.db`.
    """
    db_dir = tmp_path_factory.mktemp("db", numbered=True)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("NEWS_API_KEY", "")
    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("FRED_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_dir / 'jobs.db'}")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]
