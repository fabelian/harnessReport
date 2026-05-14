"""POST /api/analyze — runs the full pipeline and streams progress as SSE.

Two entrypoints:

- `POST /api/analyze` (SSE) — desktop clients that can hold a long fetch
  stream open. Yields per-step events for live progress.
- `POST /api/analyze/start` — fire-and-forget. Returns `{jobId}` as soon as
  the orchestrator emits `job_start`, then keeps running detached. Use this
  from clients where intermediate proxies (mobile carriers, hotel WiFi)
  drop SSE responses. Clients poll `GET /api/jobs/<id>` for results.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.orchestrator import run_analysis
from app.schemas.inputs import AnalyzeRequest
from app.utils.sse import to_sse_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analyze"])


# Strong references to detached background tasks. Without this set, the
# tasks would be eligible for garbage collection while still running.
_DETACHED_TASKS: set[asyncio.Task] = set()


@router.post("/analyze")
async def analyze(req: AnalyzeRequest) -> EventSourceResponse:
    """Run analysis for one asset. Returns a Server-Sent Events stream.

    Browser clients should consume with `fetch` + ReadableStream parsing
    (native `EventSource` is GET-only).
    """
    logger.info(
        "analyze request | asset=%s | as_of=%s | model=%s",
        req.asset, req.as_of_date, req.model.value,
    )
    return EventSourceResponse(
        to_sse_stream(run_analysis(req)),
        ping=15,
    )


@router.post("/analyze/start")
async def analyze_start(req: AnalyzeRequest) -> dict:
    """Kick off a detached analysis run and return the jobId immediately.

    This is the streaming-unreliable client path: instead of holding an SSE
    connection open for 1-3 minutes, the client gets back `{jobId}` in a
    fraction of a second and polls `/api/jobs/<jobId>` until completion.
    """
    logger.info(
        "analyze/start request | asset=%s | as_of=%s | model=%s",
        req.asset, req.as_of_date, req.model.value,
    )
    loop = asyncio.get_running_loop()
    job_id_fut: asyncio.Future[str] = loop.create_future()

    async def _runner() -> None:
        try:
            async for evt in run_analysis(req):
                if evt.event == "job_start" and not job_id_fut.done():
                    job_id_fut.set_result(evt.data["jobId"])
                # Discard the event; work happens as a side effect of the
                # generator running (data fetch, LLM calls, persistence).
        except Exception as exc:  # pragma: no cover — surfaces in jobs DB
            logger.exception("detached analysis failed")
            if not job_id_fut.done():
                job_id_fut.set_exception(exc)

    task = asyncio.create_task(_runner(), name=f"analyze-detached:{req.asset}")
    _DETACHED_TASKS.add(task)
    task.add_done_callback(_DETACHED_TASKS.discard)

    job_id = await job_id_fut
    return {"jobId": job_id}
