"""GET /api/jobs and GET /api/jobs/{id} — completed analysis retrieval."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.storage import jobs as job_store

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(limit: int = Query(50, ge=1, le=200)) -> dict:
    rows = await job_store.list_jobs(limit=limit)
    return {"jobs": rows, "count": len(rows)}


@router.get("/{job_id}")
async def get_job(job_id: str) -> job_store.JobRecord:
    record = await job_store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    return record
