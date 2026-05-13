"""Error-path tests: bad ticker, OpenRouter rate limit, malformed responses."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.fundamental import FundamentalAgent
from app.agents.base import AgentExecutionError
from app.data.resolver import ResolverError, resolve
from app.openrouter import ChatResult, OpenRouterClient, OpenRouterError
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
from app.storage.jobs import get_job


# --- Resolver --------------------------------------------------------------

async def test_resolver_rejects_empty_string() -> None:
    with pytest.raises(ResolverError):
        await resolve("")


async def test_resolver_raises_when_yfinance_returns_no_metadata() -> None:
    class _FakeTicker:
        info: dict = {}  # no symbol, no name, no regularMarketPrice

    with patch("app.data.resolver.yf.Ticker", return_value=_FakeTicker()):
        with pytest.raises(ResolverError):
            await resolve("NOPETICKER")


# --- Orchestrator: bad ticker propagates to error event ---------------------

async def test_orchestrator_emits_error_when_resolver_fails(temp_db: Path) -> None:
    await init_db()
    with patch(
        "app.orchestrator.fetch_all",
        new=AsyncMock(side_effect=ResolverError("no metadata for BAD")),
    ):
        events = []
        async for evt in run_analysis(AnalyzeRequest(asset="BAD")):
            events.append((evt.event, json.loads(evt.data_json())))

    types = [e[0] for e in events]
    assert "error" in types
    assert types[-1] == "done"
    assert events[-1][1]["ok"] is False

    job_id = events[0][1]["jobId"]
    record = await get_job(job_id)
    assert record is not None
    assert record.status == "failed"


# --- Agent: OpenRouter retries then fails -----------------------------------

def _bad_response() -> ChatResult:
    return ChatResult(content="not valid json", model="openai/gpt-oss-120b")


def _good_fundamental_response() -> ChatResult:
    payload = {
        "summary": "ok",
        "financial_trend": [],
        "valuation_metrics": [],
        "key_drivers": [],
        "risks": [],
        "scenarios": [],
        "data_caveats": [],
    }
    return ChatResult(
        content=json.dumps(payload),
        model="openai/gpt-oss-120b",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )


def _make_mock_client(side_effects: list) -> OpenRouterClient:
    client = OpenRouterClient.__new__(OpenRouterClient)
    client.client = None  # type: ignore[attr-defined]
    client.settings = None  # type: ignore[attr-defined]
    client.chat = AsyncMock(side_effect=side_effects)  # type: ignore[attr-defined]
    return client


def _minimal_data() -> AnalysisData:
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


async def test_agent_raises_when_openrouter_returns_garbage_twice() -> None:
    """Agent retries once on parse failure; second failure raises."""
    client = _make_mock_client([_bad_response(), _bad_response()])
    agent = FundamentalAgent(client=client)
    with pytest.raises(AgentExecutionError) as exc_info:
        await agent.run(_minimal_data())
    assert "fundamental" in str(exc_info.value).lower()
    assert client.chat.await_count == 2  # type: ignore[attr-defined]


async def test_agent_recovers_on_second_attempt_with_valid_json() -> None:
    client = _make_mock_client([_bad_response(), _good_fundamental_response()])
    agent = FundamentalAgent(client=client)
    run = await agent.run(_minimal_data())
    assert run.retried is True
    assert run.output.summary == "ok"


# --- OpenRouter wrapper: API surface ----------------------------------------

async def test_openrouter_raises_on_underlying_api_error() -> None:
    """`chat` should bubble `OpenRouterError` when the SDK raises."""
    client = OpenRouterClient()

    class _FakeAPIError(Exception):
        pass

    async def _explode(**kwargs):
        raise _FakeAPIError("boom")

    # Bypass retry via short-circuited mock that raises a non-retryable error.
    client._client.chat = type("X", (), {"completions": type("Y", (), {"create": _explode})()})  # type: ignore[attr-defined]

    with pytest.raises(OpenRouterError):
        await client.chat(system="s", user="u")
