"""End-to-end orchestrator test with all external calls mocked."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.base import AgentRun
from app.orchestrator import run_analysis
from app.schemas.data import (
    AnalysisData,
    AssetMeta,
    FinancialRow,
    Fundamentals,
    KeyRatios,
    MacroSnapshot,
    NewsBundle,
    PriceSeries,
    PriceSummary,
    TechnicalIndicators,
)
from app.schemas.inputs import AnalyzeRequest, ModelChoice
from app.schemas.outputs import (
    Claim,
    FundamentalOutput,
    IndustryOutput,
    Level,
    MacroFactor,
    MacroOutput,
    ReviewerOutput,
    Scenario,
    SentimentOutput,
    SentimentSignal,
    TechnicalOutput,
    ValuationMetric,
)
from app.storage.db import init_db
from app.storage.jobs import get_job


def _analysis_data() -> AnalysisData:
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
            ticker="NVDA",
            as_of_date=date(2026, 5, 13),
            quarters=[FinancialRow(period="2026Q1", revenue=44e9, eps=0.95)],
            ratios=KeyRatios(pe_trailing=55.0),
        ),
        news=NewsBundle(
            ticker="NVDA", as_of_date=date(2026, 5, 13), items=[], provider="none"
        ),
        macro=MacroSnapshot(as_of_date=date(2026, 5, 13), provider="none"),
    )


def _fund_run() -> AgentRun:
    return AgentRun(
        role="fundamental",
        output=FundamentalOutput(
            summary="펀더멘털 요약",
            financial_trend=[],
            valuation_metrics=[ValuationMetric(metric="PER (TTM)", value=55.0)],
            key_drivers=[Claim(text="데이터센터 성장", label="fact")],
            risks=[Claim(text="경쟁 심화", label="opinion")],
            scenarios=[
                Scenario(
                    name="base",
                    target_range_low=900.0,
                    target_range_high=1000.0,
                )
            ],
            data_caveats=["부문별 OP 미공개"],
        ),
        model="openai/gpt-oss-120b",
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
    )


def _tech_run() -> AgentRun:
    return AgentRun(
        role="technical",
        output=TechnicalOutput(
            summary="기술 요약",
            trend="정배열",
            moving_averages={"ma20": 890.0, "ma50": 850.0},
            momentum="RSI 62",
            levels=[Level(kind="support", price=850.0)],
            scenarios=[Scenario(name="bullish")],
            data_caveats=["후행성"],
        ),
        model="openai/gpt-oss-120b",
        prompt_tokens=800,
        completion_tokens=300,
        total_tokens=1100,
    )


def _industry_run() -> AgentRun:
    return AgentRun(
        role="industry",
        output=IndustryOutput(
            summary="산업 요약",
            cycle_phase="expansion",
            demand_drivers=[],
            supply_constraints=[],
            competitors=[],
            risks=[],
            data_caveats=[],
        ),
        model="openai/gpt-oss-120b",
        prompt_tokens=500,
        completion_tokens=200,
        total_tokens=700,
    )


def _macro_run() -> AgentRun:
    return AgentRun(
        role="macro",
        output=MacroOutput(
            summary="거시 요약",
            factors=[MacroFactor(label="Fed Funds Rate", value="4.50%", trend="stable")],
            scenario_bias="tailwind",
            data_caveats=[],
        ),
        model="openai/gpt-oss-120b",
        prompt_tokens=400,
        completion_tokens=200,
        total_tokens=600,
    )


def _sentiment_run() -> AgentRun:
    return AgentRun(
        role="sentiment",
        output=SentimentOutput(
            summary="심리 요약",
            overall_tone="bullish",
            news_signals=[
                SentimentSignal(name="earnings beat", direction="bullish")
            ],
            data_caveats=[],
        ),
        model="openai/gpt-oss-120b",
        prompt_tokens=500,
        completion_tokens=300,
        total_tokens=800,
    )


def _rev_run() -> AgentRun:
    return AgentRun(
        role="reviewer",
        output=ReviewerOutput(
            final_report_markdown="# NVDA 분석 보고서\n\n본문...",
            discrepancies=[],
            open_questions=["부문별 OP 미확보"],
            used_model="openai/gpt-oss-120b",
        ),
        model="openai/gpt-oss-120b",
        prompt_tokens=2000,
        completion_tokens=1500,
        total_tokens=3500,
    )


async def _collect_events(req: AnalyzeRequest, persist: bool = True) -> list[dict]:
    events: list[dict] = []
    async for evt in run_analysis(req, persist=persist):
        events.append({"event": evt.event, "data": json.loads(evt.data_json())})
    return events


@pytest.fixture
def _mock_pipeline():
    """Patch fetch_all + each agent's `run` method (5 analysts + reviewer)."""
    with (
        patch(
            "app.orchestrator.fetch_all",
            new=AsyncMock(return_value=_analysis_data()),
        ),
        patch(
            "app.agents.fundamental.FundamentalAgent.run",
            new=AsyncMock(return_value=_fund_run()),
        ),
        patch(
            "app.agents.technical.TechnicalAgent.run",
            new=AsyncMock(return_value=_tech_run()),
        ),
        patch(
            "app.agents.industry.IndustryAgent.run",
            new=AsyncMock(return_value=_industry_run()),
        ),
        patch(
            "app.agents.macro.MacroAgent.run",
            new=AsyncMock(return_value=_macro_run()),
        ),
        patch(
            "app.agents.sentiment.SentimentAgent.run",
            new=AsyncMock(return_value=_sentiment_run()),
        ),
        patch(
            "app.agents.reviewer.ReviewerAgent.run",
            new=AsyncMock(return_value=_rev_run()),
        ),
    ):
        yield


async def test_orchestrator_emits_expected_event_sequence(
    _mock_pipeline, temp_db: Path
) -> None:
    await init_db()
    req = AnalyzeRequest(asset="NVDA", as_of_date=date(2026, 5, 13))
    events = await _collect_events(req)

    types = [e["event"] for e in events]
    assert types[0] == "job_start"
    assert "data_fetch_start" in types
    assert "data_fetch_done" in types
    assert types.count("agent_start") == 5
    assert types.count("agent_done") == 5
    assert "reviewer_start" in types
    assert "reviewer_done" in types
    assert types[-1] == "done"

    done_event = events[-1]
    assert done_event["data"]["ok"] is True
    # Sum of all 5 analyst + reviewer token totals
    assert done_event["data"]["tokens"]["total"] == (
        1500 + 1100 + 700 + 600 + 800 + 3500
    )


async def test_orchestrator_persists_completed_job(
    _mock_pipeline, temp_db: Path
) -> None:
    await init_db()
    req = AnalyzeRequest(asset="NVDA", model=ModelChoice.gpt_oss_120b)
    events = await _collect_events(req)
    job_id = events[0]["data"]["jobId"]

    record = await get_job(job_id)
    assert record is not None
    assert record.status == "completed"
    assert record.asset == "NVDA"
    assert record.reviewer_report.startswith("# NVDA")  # type: ignore[union-attr]
    assert record.fundamental["summary"] == "펀더멘털 요약"  # type: ignore[index]


async def test_orchestrator_handles_data_fetch_failure(temp_db: Path) -> None:
    await init_db()
    with patch(
        "app.orchestrator.fetch_all",
        new=AsyncMock(side_effect=RuntimeError("yfinance down")),
    ):
        req = AnalyzeRequest(asset="NVDA")
        events = await _collect_events(req)

    types = [e["event"] for e in events]
    assert "error" in types
    assert types[-1] == "done"
    assert events[-1]["data"]["ok"] is False

    job_id = events[0]["data"]["jobId"]
    record = await get_job(job_id)
    assert record is not None
    assert record.status == "failed"
    assert "data_fetch" in (record.error or "")


async def test_orchestrator_continues_when_one_agent_fails(temp_db: Path) -> None:
    await init_db()
    with (
        patch(
            "app.orchestrator.fetch_all",
            new=AsyncMock(return_value=_analysis_data()),
        ),
        patch(
            "app.agents.fundamental.FundamentalAgent.run",
            new=AsyncMock(return_value=_fund_run()),
        ),
        patch(
            "app.agents.technical.TechnicalAgent.run",
            new=AsyncMock(side_effect=RuntimeError("technical boom")),
        ),
        patch(
            "app.agents.industry.IndustryAgent.run",
            new=AsyncMock(return_value=_industry_run()),
        ),
        patch(
            "app.agents.macro.MacroAgent.run",
            new=AsyncMock(return_value=_macro_run()),
        ),
        patch(
            "app.agents.sentiment.SentimentAgent.run",
            new=AsyncMock(return_value=_sentiment_run()),
        ),
        patch(
            "app.agents.reviewer.ReviewerAgent.run",
            new=AsyncMock(return_value=_rev_run()),
        ),
    ):
        req = AnalyzeRequest(asset="NVDA")
        events = await _collect_events(req)

    types = [e["event"] for e in events]
    # technical errored; fundamental + industry + macro + sentiment + reviewer ran
    assert types.count("agent_done") == 4
    assert "reviewer_done" in types
    assert types[-1] == "done"
    assert events[-1]["data"]["ok"] is True
