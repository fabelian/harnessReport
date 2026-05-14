"""End-to-end analysis pipeline (5 analysts + 1 reviewer).

Yields `SSEEvent`s as the run progresses. The event stream is intentionally
verbose so the frontend can render a chronological log: every external API
call (yfinance, FRED, news provider, OpenRouter) shows up as start/done
events with elapsed_ms, and every error includes the function name + tail
of the traceback so failures can be pinpointed without backend log access.

    job_start
    → data_fetch_start
    → data_fetch_progress (per source: resolver, prices, fundamentals, news, macro)
    → data_fetch_done
    → (agent_start × N)
    → (agent_step × many — llm_request, llm_response, parse, validate, retry)
    → (agent_done × N in completion order)
    → reviewer_start
    → (reviewer_step × many)
    → reviewer_done
    → done

On any unrecoverable failure the orchestrator emits an `error` event and a
final `done` event so the SSE stream always closes cleanly.
"""
from __future__ import annotations

import asyncio
import logging
import time
import traceback
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

from app.agents.base import AgentRun
from app.agents.fundamental import FundamentalAgent
from app.agents.industry import IndustryAgent
from app.agents.macro import MacroAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.sentiment import SentimentAgent
from app.agents.technical import TechnicalAgent
from app.data.fetcher import fetch_all
from app.schemas.data import AnalysisData
from app.schemas.events import SSEEvent
from app.schemas.inputs import AnalyzeRequest
from app.schemas.outputs import (
    FundamentalOutput,
    IndustryOutput,
    MacroOutput,
    ReviewerOutput,
    SentimentOutput,
    TechnicalOutput,
)
from app.storage import jobs as job_store

logger = logging.getLogger(__name__)

# Order matters only for SSE event emission and persistence labels.
ANALYST_ROLES: tuple[str, ...] = (
    "fundamental",
    "technical",
    "industry",
    "macro",
    "sentiment",
)


def _agent_done_payload(run: AgentRun, *, elapsed_ms: int | None = None) -> dict:
    payload: dict = {
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
    if elapsed_ms is not None:
        payload["elapsedMs"] = elapsed_ms
    return payload


def _error_payload(
    *,
    stage: str,
    message: str,
    function: str | None = None,
    elapsed_ms: int | None = None,
    agent: str | None = None,
) -> dict:
    """Build an error event payload with diagnostic detail.

    `function` and the traceback tail come from sys.exc_info() if called
    inside an except block — captured via traceback.format_exc().
    """
    payload: dict = {"stage": stage, "message": message}
    if agent is not None:
        payload["agent"] = agent
    if function is not None:
        payload["function"] = function
    if elapsed_ms is not None:
        payload["elapsedMs"] = elapsed_ms
    tb = traceback.format_exc()
    if tb and tb.strip() != "NoneType: None":
        # Last ~10 lines is usually plenty to locate the failing call.
        lines = [line for line in tb.splitlines() if line.strip()]
        payload["tracebackTail"] = "\n".join(lines[-10:])
        # Best-effort: pull the deepest frame's "File ... line N, in func".
        if function is None:
            for line in reversed(lines):
                if line.lstrip().startswith("File "):
                    payload["function"] = line.strip()
                    break
    return payload


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

    def _ms() -> int:
        return int((time.monotonic() - started) * 1000)

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

    yield SSEEvent("data_fetch_start", {"asset": request.asset, "elapsedMs": _ms()})

    # fetch_all runs sources in parallel and invokes on_progress(source, status)
    # at start + completion. Pipe those into SSE via an asyncio.Queue so we
    # interleave them with the await on fetch_all itself. Track per-source
    # start times so we can attach elapsed_ms to each "done"/"error" event.
    fetch_q: asyncio.Queue[tuple[str, str] | None] = asyncio.Queue()
    fetch_started_at: dict[str, float] = {}

    def _on_fetch_progress(source: str, status: str) -> None:
        # Called from inside fetch_all. Synchronous put_nowait is safe here
        # because the queue is unbounded and we're on the same event loop.
        fetch_q.put_nowait((source, status))

    fetch_task = asyncio.create_task(
        fetch_all(request.asset, request.as_of_date, on_progress=_on_fetch_progress),
        name="fetch_all",
    )
    data: AnalysisData | None = None
    try:
        # Drain progress events while fetch_task runs.
        while True:
            getter = asyncio.create_task(fetch_q.get())
            done_set, _ = await asyncio.wait(
                {fetch_task, getter}, return_when=asyncio.FIRST_COMPLETED
            )
            if getter in done_set:
                source, status = getter.result()
                if status == "start":
                    fetch_started_at[source] = time.monotonic()
                    yield SSEEvent(
                        "data_fetch_progress",
                        {"source": source, "status": "start", "elapsedMs": _ms()},
                    )
                else:  # done | error
                    src_elapsed = (
                        int((time.monotonic() - fetch_started_at[source]) * 1000)
                        if source in fetch_started_at
                        else None
                    )
                    yield SSEEvent(
                        "data_fetch_progress",
                        {
                            "source": source,
                            "status": status,
                            "sourceElapsedMs": src_elapsed,
                            "elapsedMs": _ms(),
                        },
                    )
            else:
                getter.cancel()
            if fetch_task in done_set:
                # Drain any remaining progress events queued before completion.
                while not fetch_q.empty():
                    source, status = fetch_q.get_nowait()
                    src_elapsed = (
                        int((time.monotonic() - fetch_started_at[source]) * 1000)
                        if source in fetch_started_at and status != "start"
                        else None
                    )
                    yield SSEEvent(
                        "data_fetch_progress",
                        {
                            "source": source,
                            "status": status,
                            "sourceElapsedMs": src_elapsed,
                            "elapsedMs": _ms(),
                        },
                    )
                data = fetch_task.result()
                break
    except Exception as exc:
        logger.exception("data_fetch failed")
        yield SSEEvent(
            "error",
            _error_payload(
                stage="data_fetch",
                message=str(exc),
                function="app.data.fetcher.fetch_all",
                elapsed_ms=_ms(),
            ),
        )
        await _finalize_failure(job_id, started, f"data_fetch: {exc}", persist=persist)
        yield SSEEvent("done", _done_payload(job_id, started, ok=False))
        return

    yield SSEEvent(
        "data_fetch_done",
        {"summary": data.summary(), "errors": data.errors, "elapsedMs": _ms()},
    )

    # --- 2. Analysts in parallel --------------------------------------------

    analyst_specs = [
        ("fundamental", FundamentalAgent()),
        ("technical", TechnicalAgent()),
        ("industry", IndustryAgent()),
        ("macro", MacroAgent()),
        ("sentiment", SentimentAgent()),
    ]

    # Each agent task pushes:
    #  - SSEEvent for live agent_step events
    #  - ("done", role, AgentRun) on success
    #  - ("error", role, message, traceback) on failure
    # The orchestrator drains the queue while waiting for tasks to finish.
    agent_q: asyncio.Queue = asyncio.Queue()
    agent_started_at: dict[str, float] = {}

    def _make_agent_step(role: str) -> Callable[[str, dict], Awaitable[None]]:
        async def emit(step: str, payload: dict) -> None:
            evt_payload = {
                "agent": role,
                "step": step,
                "elapsedMs": _ms(),
                "agentElapsedMs": int(
                    (time.monotonic() - agent_started_at[role]) * 1000
                )
                if role in agent_started_at
                else None,
                **payload,
            }
            await agent_q.put(SSEEvent("agent_step", evt_payload))
        return emit

    async def _run_one_analyst(role: str, agent) -> None:
        try:
            run = await agent.run(
                data, model=model_id, on_step=_make_agent_step(role)
            )
            await agent_q.put(("done", role, run))
        except Exception as exc:
            await agent_q.put(("error", role, str(exc), traceback.format_exc()))

    tasks: list[asyncio.Task] = []
    for role, agent in analyst_specs:
        agent_started_at[role] = time.monotonic()
        yield SSEEvent("agent_start", {"agent": role, "elapsedMs": _ms()})
        tasks.append(asyncio.create_task(_run_one_analyst(role, agent), name=role))

    outputs: dict[str, AgentRun | None] = {role: None for role in ANALYST_ROLES}
    agent_errors: list[str] = []
    remaining = len(tasks)
    while remaining > 0:
        item = await agent_q.get()
        if isinstance(item, SSEEvent):
            yield item
            continue
        kind = item[0]
        role = item[1]
        agent_elapsed = int((time.monotonic() - agent_started_at[role]) * 1000)
        if kind == "done":
            run: AgentRun = item[2]
            _accumulate(run)
            outputs[run.role] = run
            yield SSEEvent("agent_done", _agent_done_payload(run, elapsed_ms=agent_elapsed))
        else:  # error
            message = item[2]
            tb = item[3]
            logger.warning("agent[%s] failed: %s", role, message)
            agent_errors.append(f"{role}: {message}")
            payload = {
                "stage": "agent",
                "agent": role,
                "message": message,
                "elapsedMs": _ms(),
                "agentElapsedMs": agent_elapsed,
            }
            if tb and tb.strip() != "NoneType: None":
                lines = [ln for ln in tb.splitlines() if ln.strip()]
                payload["tracebackTail"] = "\n".join(lines[-10:])
                for ln in reversed(lines):
                    if ln.lstrip().startswith("File "):
                        payload["function"] = ln.strip()
                        break
            yield SSEEvent("error", payload)
        remaining -= 1

    if not any(outputs.values()):
        await _finalize_failure(
            job_id,
            started,
            "all agents failed: " + "; ".join(agent_errors),
            persist=persist,
        )
        yield SSEEvent("done", _done_payload(job_id, started, ok=False))
        return

    # --- 3. Reviewer ---------------------------------------------------------

    reviewer_started_at = time.monotonic()
    yield SSEEvent("reviewer_start", {"elapsedMs": _ms()})

    # Reviewer also emits steps live via the same queue mechanism.
    reviewer_q: asyncio.Queue = asyncio.Queue()

    async def _reviewer_step(step: str, payload: dict) -> None:
        evt_payload = {
            "step": step,
            "elapsedMs": _ms(),
            "reviewerElapsedMs": int(
                (time.monotonic() - reviewer_started_at) * 1000
            ),
            **payload,
        }
        await reviewer_q.put(SSEEvent("reviewer_step", evt_payload))

    reviewer_agent = ReviewerAgent()

    def _out(role: str):
        run = outputs.get(role)
        return run.output if run else None

    async def _run_reviewer() -> tuple[str, AgentRun | None, str | None, str | None]:
        try:
            r = await reviewer_agent.run(
                data,
                _out("fundamental"),  # type: ignore[arg-type]
                _out("technical"),  # type: ignore[arg-type]
                _out("industry"),  # type: ignore[arg-type]
                _out("macro"),  # type: ignore[arg-type]
                _out("sentiment"),  # type: ignore[arg-type]
                model=model_id,
                on_step=_reviewer_step,
            )
            return ("done", r, None, None)
        except Exception as exc:
            return ("error", None, str(exc), traceback.format_exc())

    reviewer_task = asyncio.create_task(_run_reviewer(), name="reviewer")
    while True:
        getter = asyncio.create_task(reviewer_q.get())
        done_set, _ = await asyncio.wait(
            {reviewer_task, getter}, return_when=asyncio.FIRST_COMPLETED
        )
        if getter in done_set:
            evt = getter.result()
            yield evt
        else:
            getter.cancel()
        if reviewer_task in done_set:
            while not reviewer_q.empty():
                yield reviewer_q.get_nowait()
            break

    kind, rev_run, rev_msg, rev_tb = reviewer_task.result()
    reviewer_elapsed = int((time.monotonic() - reviewer_started_at) * 1000)
    reviewer_output: ReviewerOutput | None = None
    if kind == "done" and rev_run is not None:
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
                "elapsedMs": _ms(),
                "reviewerElapsedMs": reviewer_elapsed,
            },
        )
    else:
        logger.warning("reviewer failed: %s", rev_msg)
        payload = {
            "stage": "reviewer",
            "message": rev_msg or "unknown reviewer failure",
            "elapsedMs": _ms(),
            "reviewerElapsedMs": reviewer_elapsed,
        }
        if rev_tb and rev_tb.strip() != "NoneType: None":
            lines = [ln for ln in rev_tb.splitlines() if ln.strip()]
            payload["tracebackTail"] = "\n".join(lines[-10:])
            for ln in reversed(lines):
                if ln.lstrip().startswith("File "):
                    payload["function"] = ln.strip()
                    break
        yield SSEEvent("error", payload)
        await _finalize_failure(
            job_id, started, f"reviewer: {rev_msg}", persist=persist
        )
        yield SSEEvent("done", _done_payload(job_id, started, ok=False))
        return

    # --- 4. Persist ----------------------------------------------------------

    if persist:
        try:
            await job_store.complete_job(
                job_id=job_id,
                duration_ms=_ms(),
                data_summary=data.summary(),
                fundamental=_dump(outputs.get("fundamental")),
                technical=_dump(outputs.get("technical")),
                industry=_dump(outputs.get("industry")),
                macro=_dump(outputs.get("macro")),
                sentiment=_dump(outputs.get("sentiment")),
                reviewer_report=reviewer_output.final_report_markdown,
                discrepancies=[d.model_dump() for d in reviewer_output.discrepancies],
                open_questions=reviewer_output.open_questions,
                token_usage=token_usage,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("persist complete_job failed: %s", exc)

    yield SSEEvent("done", _done_payload(job_id, started, ok=True, tokens=token_usage))


def _dump(run: AgentRun | None) -> dict | None:
    return run.output.model_dump() if run else None


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
