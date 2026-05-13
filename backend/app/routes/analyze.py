"""POST /api/analyze — runs the full pipeline and streams progress as SSE."""
from __future__ import annotations

import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.orchestrator import run_analysis
from app.schemas.inputs import AnalyzeRequest
from app.utils.sse import to_sse_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/analyze")
async def analyze(req: AnalyzeRequest) -> EventSourceResponse:
    """Run analysis for one asset. Returns a Server-Sent Events stream.

    Browser clients should consume with `fetch` + ReadableStream parsing
    (native `EventSource` is GET-only).
    """
    logger.info("analyze request | asset=%s | as_of=%s | model=%s",
                req.asset, req.as_of_date, req.model.value)
    return EventSourceResponse(
        to_sse_stream(run_analysis(req)),
        ping=15,
    )
