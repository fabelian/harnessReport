"""Storage CRUD against a temp SQLite database."""
from __future__ import annotations

from pathlib import Path

from app.storage.db import database_path, init_db
from app.storage.jobs import (
    JobRecord,
    complete_job,
    create_job,
    fail_job,
    get_job,
    list_jobs,
)


async def test_create_and_complete_job_round_trip(temp_db: Path) -> None:
    assert Path(database_path()).name == "test_jobs.db"
    await init_db()
    await create_job(
        job_id="job-1",
        asset="NVDA",
        as_of_date="2026-05-13",
        model="openai/gpt-oss-120b",
    )
    record = await get_job("job-1")
    assert record is not None
    assert record.status == "running"

    await complete_job(
        job_id="job-1",
        duration_ms=42000,
        data_summary={"ticker": "NVDA"},
        fundamental={"summary": "x"},
        technical={"summary": "y"},
        reviewer_report="# report",
        discrepancies=[{"metric": "PER", "values": ["a", "b"], "resolution": "a"}],
        open_questions=["q1"],
        token_usage={"prompt": 1000, "completion": 500, "total": 1500},
    )

    record2 = await get_job("job-1")
    assert isinstance(record2, JobRecord)
    assert record2.status == "completed"
    assert record2.duration_ms == 42000
    assert record2.data_summary == {"ticker": "NVDA"}
    assert record2.reviewer_report == "# report"
    assert record2.discrepancies == [
        {"metric": "PER", "values": ["a", "b"], "resolution": "a"}
    ]
    assert record2.token_usage == {"prompt": 1000, "completion": 500, "total": 1500}


async def test_fail_job_records_error(temp_db: Path) -> None:
    await init_db()
    await create_job(job_id="job-fail", asset="X", as_of_date="2026-05-13", model="m")
    await fail_job(job_id="job-fail", error="boom", duration_ms=100)
    record = await get_job("job-fail")
    assert record is not None
    assert record.status == "failed"
    assert record.error == "boom"


async def test_list_jobs_orders_by_created_desc(temp_db: Path) -> None:
    await init_db()
    for i, asset in enumerate(["AAA", "BBB", "CCC"]):
        await create_job(job_id=f"j-{i}", asset=asset, as_of_date="2026-05-13", model="m")
    rows = await list_jobs(limit=10)
    assert len(rows) == 3
    # Newest first
    assets = [r["asset"] for r in rows]
    assert assets[0] == "CCC"
    assert assets[-1] == "AAA"


async def test_get_missing_job_returns_none(temp_db: Path) -> None:
    await init_db()
    assert await get_job("nope") is None
