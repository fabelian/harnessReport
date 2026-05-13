"""Job record CRUD on the `jobs` table."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.storage.db import connect

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    # Microsecond precision so ORDER BY created_at can break ties between
    # jobs created in quick succession (e.g. in tests / smoke loops).
    return datetime.now(tz=timezone.utc).isoformat(timespec="microseconds")


def _dump(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(), default=str, ensure_ascii=False)
    return json.dumps(value, default=str, ensure_ascii=False)


def _load(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


class JobRecord(BaseModel):
    """Serialized view of a row in `jobs`."""

    model_config = ConfigDict(extra="ignore")

    id: str
    asset: str
    as_of_date: str
    model: str
    status: str
    created_at: str
    completed_at: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    data_summary: dict | None = None
    fundamental: dict | None = None
    technical: dict | None = None
    industry: dict | None = None
    macro: dict | None = None
    sentiment: dict | None = None
    reviewer_report: str | None = None
    discrepancies: list | None = None
    open_questions: list | None = None
    token_usage: dict | None = None


async def create_job(
    *,
    job_id: str,
    asset: str,
    as_of_date: str,
    model: str,
) -> None:
    async with connect() as db:
        await db.execute(
            "INSERT INTO jobs (id, asset, as_of_date, model, status, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (job_id, asset, as_of_date, model, "running", _now_iso()),
        )
        await db.commit()


async def complete_job(
    *,
    job_id: str,
    duration_ms: int,
    data_summary: dict | None,
    fundamental: Any,
    technical: Any,
    industry: Any = None,
    macro: Any = None,
    sentiment: Any = None,
    reviewer_report: str | None,
    discrepancies: Any,
    open_questions: Any,
    token_usage: dict | None,
) -> None:
    async with connect() as db:
        await db.execute(
            """
            UPDATE jobs SET
                status='completed',
                completed_at=?,
                duration_ms=?,
                data_summary=?,
                fundamental=?,
                technical=?,
                industry=?,
                macro=?,
                sentiment=?,
                reviewer_report=?,
                discrepancies=?,
                open_questions=?,
                token_usage=?
            WHERE id=?
            """,
            (
                _now_iso(),
                duration_ms,
                _dump(data_summary),
                _dump(fundamental),
                _dump(technical),
                _dump(industry),
                _dump(macro),
                _dump(sentiment),
                reviewer_report,
                _dump(discrepancies),
                _dump(open_questions),
                _dump(token_usage),
                job_id,
            ),
        )
        await db.commit()


async def fail_job(*, job_id: str, error: str, duration_ms: int | None = None) -> None:
    async with connect() as db:
        await db.execute(
            "UPDATE jobs SET status='failed', completed_at=?, duration_ms=?, error=? WHERE id=?",
            (_now_iso(), duration_ms, error, job_id),
        )
        await db.commit()


async def get_job(job_id: str) -> JobRecord | None:
    async with connect() as db:
        async with db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)) as cur:
            row = await cur.fetchone()
    if row is None:
        return None
    return JobRecord(
        id=row["id"],
        asset=row["asset"],
        as_of_date=row["as_of_date"],
        model=row["model"],
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        duration_ms=row["duration_ms"],
        error=row["error"],
        data_summary=_load(row["data_summary"]),
        fundamental=_load(row["fundamental"]),
        technical=_load(row["technical"]),
        industry=_load(row["industry"]) if "industry" in row.keys() else None,
        macro=_load(row["macro"]) if "macro" in row.keys() else None,
        sentiment=_load(row["sentiment"]) if "sentiment" in row.keys() else None,
        reviewer_report=row["reviewer_report"],
        discrepancies=_load(row["discrepancies"]),
        open_questions=_load(row["open_questions"]),
        token_usage=_load(row["token_usage"]),
    )


async def list_jobs(*, limit: int = 50) -> list[dict]:
    """Lightweight listing — omits large payloads for performance."""
    async with connect() as db:
        async with db.execute(
            "SELECT id, asset, as_of_date, model, status, created_at, completed_at, "
            "duration_ms, error FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


__all__ = [
    "JobRecord",
    "create_job",
    "complete_job",
    "fail_job",
    "get_job",
    "list_jobs",
]
