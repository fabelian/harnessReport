"""End-to-end analysis pipeline.

Yields `SSEEvent`s as the run progresses:

    job_start → data_fetch_start → data_fetch_done →
    (agent_start × 2) → (agent_done × 2 in completion order) →
    reviewer_start → reviewer_done → done

On any unrecoverable failure the orchestrator emits an `error` event and a
final `done` event so the SSE stream always closes cleanly.

The orchestrator is the single place that knows about persistence; routes
just consume the async iterator.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator

from app.agents.base import AgentRun
from app.agents.fundamental import FundamentalAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.technical import TechnicalAgent
from app.data.fetcher import fetch_all
from app.schemas.data import AnalysisData
from app.schemas.events import SSEEvent
from app.schemas.inputs import AnalyzeRequest
from app.schemas.outputs import FundamentalOutput, ReviewerOutput, TechnicalOutput
from app.storage import jobs as job_store

logger = logging.getLogger(__name__)


def _agent_done_payload(run: AgentRun) -> dict:
    return {
        "agent": run.role,
        "output": run.output.model_dump(mode="json"),
        "tokens": {
            "prompt": run.prompt_tokens,
            "completion": run.completion_tokens,
            "total": run.total_tokens,
        },
        "model": run.model,
        "retried": run.retried,
    }


async def run_analysis(
    request: AnalyzeRequest,
    *,
    persist: bool = True,
) -> AsyncIterator[SSEEvent]:
    """Async generator yielding SSE events for one analysis run."""
    job_id = uuid.uuid4().hex
    model_id = request.model.value
    started = time.monotonic()
    token_usage = {"prompt": 0, "completion": 0, "total": 0}

    def _accumulate(run: AgentRun) -> None:
        token_usage["prompt"] += run.prompt_tokens or 0
        token_usage["completion"] += run.completion_tokens or 0
        token_usage["total"] += run.total_tokens or 0

    yield SSEEvent(
        "job_start",
        {
            "jobId": job_id,
            "asset": request.asset,
            "asOfDate": request.as_of_date.isoformat(),
            "model": model_id,
        },
    )

    if persist:
        try:
            await job_store.create_job(
                job_id=job_id,
                asset=request.asset,
                as_of_date=request.as_of_date.isoformat(),
                model=model_id,
            )
        except Exception as exc:  # pragma: no cover — DB failures are non-fatal
            logger.warning("persist create_job failed: %s", exc)
            persist = False

    # --- 1. Data fetch -------------------------------------------------------

    yield SSEEvent("data_fetch_start", {"asset": request.asset})
    data: AnalysisData | None = None
    try:
        data = await fetch_all(request.asset, request.as_of_date)
    except Exception as exc:
        logger.exception("data_fetch failed")
        yield SSEEvent(
            "error",
            {"stage": "data_fetch", "message": str(exc)},
        )
        await _finalize_failure(job_id, started, f"data_fetch: {exc}", persist=persist)
        yield SSEEvent("done", _done_payload(job_id, started, ok=False))
        return

    yield SSEEvent(
        "data_fetch_done",
        {"summary": data.summary(), "errors": data.errors},
    )

    # --- 2. Analysts in parallel --------------------------------------------

    fundamental_agent = FundamentalAgent()
    technical_agent = TechnicalAgent()

    fund_task = asyncio.create_task(
        fundamental_agent.run(data, model=model_id),
        name="fundamental",
    )
    tech_task = asyncio.create_task(
        technical_agent.run(data, model=model_id),
        name="technical",
    )

    yield SSEEvent("agent_start", {"agent": "fundamental"})
    yield SSEEvent("agent_start", {"agent": "technical"})

    fund_output: FundamentalOutput | None = None
    tech_output: TechnicalOutput | None = None
    agent_errors: list[str] = []

    pending = {fund_task, tech_task}
    while pending:
        done, pending = await asyncio.wait(
            pending, return_when=asyncio.FIRST_COMPLETED
        )
        for finished in done:
            label = finished.get_name()
            try:
                run = finished.result()
                _accumulate(run)
                if run.role == "fundamental":
                    fund_output = run.output  # type: ignore[assignment]
                elif run.role == "technical":
                    tech_output = run.output  # type: ignore[assignment]
                yield SSEEvent("agent_done", _agent_done_payload(run))
            except Exception as exc:
                logger.exception("agent[%s] failed", label)
                agent_errors.append(f"{label}: {exc}")
                yield SSEEvent(
                    "error",
                    {"stage": "agent", "agent": label, "message": str(exc)},
                )

    if fund_output is None and tech_output is None:
        await _finalize_failure(
            job_id,
            started,
            "all agents failed: " + "; ".join(agent_errors),
            persist=persist,
        )
        yield SSEEvent("done", _done_payload(job_id, started, ok=False))
        return

    # --- 3. Reviewer ---------------------------------------------------------

    yield SSEEvent("reviewer_start", {})
    reviewer_agent = ReviewerAgent()
    reviewer_output: ReviewerOutput | None = None
    try:
        rev_run = await reviewer_agent.run(
            data, fund_output, tech_output, model=model_id
        )
        _accumulate(rev_run)
        reviewer_output = rev_run.output  # type: ignore[assignment]
        yield SSEEvent(
            "reviewer_done",
            {
                "report": reviewer_output.final_report_markdown,
                "discrepancies": [d.model_dump() for d in reviewer_output.discrepancies],
                "openQuestions": reviewer_output.open_questions,
                "tokens": {
                    "prompt": rev_run.prompt_tokens,
                    "completion": rev_run.completion_tokens,
                    "total": rev_run.total_tokens,
                },
                "model": rev_run.model,
                "retried": rev_run.retried,
            },
        )
    except Exception as exc:
        logger.exception("reviewer failed")
        yield SSEEvent("error", {"stage": "reviewer", "message": str(exc)})
        await _finalize_failure(
            job_id, started, f"reviewer: {exc}", persist=persist
        )
        yield SSEEvent("done", _done_payload(job_id, started, ok=False))
        return

    # --- 4. Persist ----------------------------------------------------------

    if persist:
        try:
            await job_store.complete_job(
                job_id=job_id,
                duration_ms=int((time.monotonic() - started) * 1000),
                data_summary=data.summary(),
                fundamental=fund_output.model_dump() if fund_output else None,
                technical=tech_output.model_dump() if tech_output else None,
                reviewer_report=reviewer_output.final_report_markdown,
                discrepancies=[d.model_dump() for d in reviewer_output.discrepancies],
                open_questions=reviewer_output.open_questions,
                token_usage=token_usage,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("persist complete_job failed: %s", exc)

    yield SSEEvent("done", _done_payload(job_id, started, ok=True, tokens=token_usage))


def _done_payload(
    job_id: str,
    started_at: float,
    *,
    ok: bool,
    tokens: dict[str, int] | None = None,
) -> dict:
    payload: dict = {
        "jobId": job_id,
        "durationMs": int((time.monotonic() - started_at) * 1000),
        "ok": ok,
    }
    if tokens is not None:
        payload["tokens"] = tokens
    return payload


async def _finalize_failure(
    job_id: str, started: float, error: str, *, persist: bool
) -> None:
    if not persist:
        return
    try:
        await job_store.fail_job(
            job_id=job_id,
            error=error,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("persist fail_job failed: %s", exc)
