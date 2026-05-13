"""Smoke tests for routes wired into the FastAPI app."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.agents.base import AgentRun
from app.main import app
from app.schemas.data import (
    AnalysisData,
    AssetMeta,
    KeyRatios,
    Fundamentals,
    MacroSnapshot,
    NewsBundle,
    PriceSeries,
    PriceSummary,
    TechnicalIndicators,
)
from app.schemas.outputs import (
    FundamentalOutput,
    ReviewerOutput,
    TechnicalOutput,
)


def _data() -> AnalysisData:
    return AnalysisData(
        asset=AssetMeta(ticker="NVDA"),
        as_of_date=date(2026, 5, 13),
        prices=PriceSeries(
            ticker="NVDA",
            as_of_date=date(2026, 5, 13),
            points=[],
            indicators=TechnicalIndicators(),
            summary=PriceSummary(as_of_close=900.0),
        ),
        fundamentals=Fundamentals(
            ticker="NVDA", as_of_date=date(2026, 5, 13), ratios=KeyRatios()
        ),
        news=NewsBundle(
            ticker="NVDA", as_of_date=date(2026, 5, 13), items=[], provider="none"
        ),
        macro=MacroSnapshot(as_of_date=date(2026, 5, 13), provider="none"),
    )


def _runs():
    return (
        AgentRun(
            role="fundamental",
            output=FundamentalOutput(summary="f", financial_trend=[]),
            model="openai/gpt-oss-120b",
            total_tokens=100,
        ),
        AgentRun(
            role="technical",
            output=TechnicalOutput(
                summary="t",
                trend="x",
                moving_averages={},
                momentum="y",
                levels=[],
            ),
            model="openai/gpt-oss-120b",
            total_tokens=100,
        ),
        AgentRun(
            role="reviewer",
            output=ReviewerOutput(final_report_markdown="# Report"),
            model="openai/gpt-oss-120b",
            total_tokens=200,
        ),
    )


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"


def test_models_endpoint_lists_choices() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/models")
        assert resp.status_code == 200
        body = resp.json()
        assert any(m["id"] == "openai/gpt-oss-120b" for m in body["models"])
        assert "default" in body


def test_analyze_streams_sse_to_done(temp_db: Path) -> None:
    fund_run, tech_run, rev_run = _runs()
    with (
        patch(
            "app.orchestrator.fetch_all", new=AsyncMock(return_value=_data())
        ),
        patch(
            "app.agents.fundamental.FundamentalAgent.run",
            new=AsyncMock(return_value=fund_run),
        ),
        patch(
            "app.agents.technical.TechnicalAgent.run",
            new=AsyncMock(return_value=tech_run),
        ),
        patch(
            "app.agents.reviewer.ReviewerAgent.run",
            new=AsyncMock(return_value=rev_run),
        ),
    ):
        with TestClient(app) as client:
            with client.stream(
                "POST",
                "/api/analyze",
                json={"asset": "NVDA", "asOfDate": "2026-05-13"},
            ) as resp:
                assert resp.status_code == 200
                body = "".join(resp.iter_text())

    # SSE body should contain the canonical event sequence
    for evt in [
        "event: job_start",
        "event: data_fetch_done",
        "event: agent_done",
        "event: reviewer_done",
        "event: done",
    ]:
        assert evt in body, f"missing {evt} in SSE body"


def test_jobs_list_and_get_404(temp_db: Path) -> None:
    with TestClient(app) as client:
        list_resp = client.get("/api/jobs")
        assert list_resp.status_code == 200
        assert "jobs" in list_resp.json()

        miss_resp = client.get("/api/jobs/does-not-exist")
        assert miss_resp.status_code == 404
