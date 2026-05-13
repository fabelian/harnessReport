"""Demo-mode end-to-end: full orchestrator with no real network calls.

When `OPENROUTER_API_KEY == "demo"` is set, `get_client()` should return the
canned `DemoOpenRouterClient`. Combined with mocked data fetcher, the whole
pipeline should complete and emit a final report.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.config import get_settings
from app.openrouter import get_client, reset_client
from app.openrouter_demo import DemoOpenRouterClient
from app.orchestrator import run_analysis
from app.schemas.data import (
    AnalysisData,
    AssetMeta,
    Fundamentals,
    KeyRatios,
    MacroSnapshot,
    NewsBundle,
    PriceSeries,
    PriceSummary,
    TechnicalIndicators,
)
from app.schemas.inputs import AnalyzeRequest
from app.storage.db import init_db


@pytest.fixture(autouse=True)
def _enable_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "demo")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    reset_client()
    yield
    reset_client()


def _data() -> AnalysisData:
    return AnalysisData(
        asset=AssetMeta(ticker="NVDA", name="NVIDIA Corp", currency="USD"),
        as_of_date=date(2026, 5, 13),
        prices=PriceSeries(
            ticker="NVDA",
            as_of_date=date(2026, 5, 13),
            points=[],
            indicators=TechnicalIndicators(ma20=890.0, rsi14=62.0),
            summary=PriceSummary(as_of_close=905.0),
        ),
        fundamentals=Fundamentals(
            ticker="NVDA", as_of_date=date(2026, 5, 13), ratios=KeyRatios()
        ),
        news=NewsBundle(
            ticker="NVDA", as_of_date=date(2026, 5, 13), items=[], provider="none"
        ),
        macro=MacroSnapshot(as_of_date=date(2026, 5, 13), provider="none"),
    )


def test_get_client_returns_demo_when_key_is_demo() -> None:
    client = get_client()
    assert isinstance(client, DemoOpenRouterClient)
    assert client.default_model  # any non-empty


async def test_full_pipeline_runs_in_demo_mode(temp_db: Path) -> None:
    await init_db()
    with patch(
        "app.orchestrator.fetch_all", new=AsyncMock(return_value=_data())
    ):
        req = AnalyzeRequest(asset="NVDA", as_of_date=date(2026, 5, 13))
        events = []
        async for evt in run_analysis(req):
            events.append((evt.event, json.loads(evt.data_json())))

    types = [e[0] for e in events]
    assert types.count("agent_done") == 2
    assert "reviewer_done" in types
    assert types[-1] == "done"
    assert events[-1][1]["ok"] is True

    # Reviewer report should reference the asset
    reviewer_done = next(e for e in events if e[0] == "reviewer_done")
    assert "NVDA" in reviewer_done[1]["report"]
    assert "DEMO" in reviewer_done[1]["report"]


async def test_demo_responses_validate_against_output_schemas(
    temp_db: Path,
) -> None:
    """Schema validation: agents accept the canned payloads without retry."""
    await init_db()
    with patch(
        "app.orchestrator.fetch_all", new=AsyncMock(return_value=_data())
    ):
        req = AnalyzeRequest(asset="NVDA")
        events = []
        async for evt in run_analysis(req):
            events.append((evt.event, json.loads(evt.data_json())))

    for ev_type, data in events:
        if ev_type == "agent_done":
            assert data["retried"] is False, f"demo response should not need retry: {data['agent']}"
