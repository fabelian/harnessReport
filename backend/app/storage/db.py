"""SQLite connection helpers (aiosqlite).

We accept a database URL like `sqlite+aiosqlite:///./jobs.db` (SQLAlchemy
style for compatibility with `.env.example`) and reduce it to a plain file
path that aiosqlite can use.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

from app.config import get_settings

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    asset           TEXT NOT NULL,
    as_of_date      TEXT NOT NULL,
    model           TEXT NOT NULL,
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    completed_at    TEXT,
    duration_ms     INTEGER,
    error           TEXT,
    data_summary    TEXT,
    fundamental     TEXT,
    technical       TEXT,
    industry        TEXT,
    macro           TEXT,
    sentiment       TEXT,
    reviewer_report TEXT,
    discrepancies   TEXT,
    open_questions  TEXT,
    token_usage     TEXT
);
CREATE INDEX IF NOT EXISTS jobs_created_idx ON jobs(created_at DESC);
"""


# Idempotent migration: add columns introduced in Phase 6 if missing.
_MIGRATIONS = [
    "ALTER TABLE jobs ADD COLUMN industry TEXT",
    "ALTER TABLE jobs ADD COLUMN macro TEXT",
    "ALTER TABLE jobs ADD COLUMN sentiment TEXT",
]


def database_path() -> str:
    """Resolve the database URL to a filesystem path for aiosqlite."""
    url = get_settings().database_url
    # Accept either "sqlite+aiosqlite:///path" or "sqlite:///path" or a bare path
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if url.startswith(prefix):
            return url[len(prefix) :] or ":memory:"
    return url


async def init_db() -> None:
    """Create the schema if it doesn't yet exist; run lightweight migrations."""
    path = database_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.executescript(_SCHEMA)
        # Best-effort additive migrations — skip if column already exists.
        for stmt in _MIGRATIONS:
            try:
                await db.execute(stmt)
            except Exception:
                pass
        await db.commit()
    logger.info("db initialised | path=%s", path)


@asynccontextmanager
async def connect() -> AsyncIterator[aiosqlite.Connection]:
    """Context manager for a single connection. Row factory returns dicts."""
    path = database_path()
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        yield db


__all__ = ["init_db", "connect", "database_path"]
