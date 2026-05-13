"""Unit tests for the analyst agents (mocked OpenRouter)."""
from __future__ import annotations

import json
from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.agents.base import AgentExecutionError
from app.agents.fundamental import FundamentalAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.technical import TechnicalAgent
from app.openrouter import ChatResult, OpenRouterClient
from app.schemas.data import (
    AnalysisData,
    AssetMeta,
    FinancialRow,
    Fundamentals,
    KeyRatios,
    MacroSnapshot,
    NewsBundle,
    PricePoint,
    PriceSeries,
    PriceSummary,
    TechnicalIndicators,
)
from app.schemas.outputs import FundamentalOutput, TechnicalOutput


@pytest.fixture
def analysis_data() -> AnalysisData:
    return AnalysisData(
        asset=AssetMeta(ticker="NVDA", name="NVIDIA Corp", currency="USD"),
        as_of_date=date(2026, 5, 13),
        prices=PriceSeries(
            ticker="NVDA",
            as_of_date=date(2026, 5, 13),
            points=[
                PricePoint(
                    date=date(2026, 5, 12),
                    open=900.0,
                    high=910.0,
                    low=895.0,
                    close=905.0,
                    volume=10_000_000,
                )
            ],
            indicators=TechnicalIndicators(ma20=890.0, ma50=850.0, ma200=700.0, rsi14=62.0),
            summary=PriceSummary(
                as_of_close=905.0,
                period_high_52w=950.0,
                period_low_52w=400.0,
                return_1m=0.05,
                return_1y=1.10,
            ),
        ),
        fundamentals=Fundamentals(
            ticker="NVDA",
            as_of_date=date(2026, 5, 13),
            quarters=[
                FinancialRow(
                    period="2026Q1",
                    revenue=44_000_000_000,
                    operating_income=29_000_000_000,
                    net_income=24_000_000_000,
                    eps=0.95,
                    op_margin=0.66,
                )
            ],
            ratios=KeyRatios(pe_trailing=55.0, pe_forward=32.0, pb=38.0, roe=0.95),
        ),
        news=NewsBundle(
            ticker="NVDA",
            as_of_date=date(2026, 5, 13),
            items=[],
            provider="none",
        ),
        macro=MacroSnapshot(as_of_date=date(2026, 5, 13), provider="none"),
    )


def _fundamental_payload() -> dict[str, Any]:
    return {
        "summary": "데이터센터 매출 호조로 매출·OP 사상 최고를 갱신했다.",
        "financial_trend": [
            {
                "period": "2026Q1",
                "revenue": 44_000_000_000,
                "operating_income": 29_000_000_000,
                "net_income": 24_000_000_000,
                "eps": 0.95,
                "op_margin": 0.66,
            }
        ],
        "valuation_metrics": [
            {"metric": "PER (TTM)", "value": 55.0, "peer_median": 30.0, "note": None},
        ],
        "key_drivers": [
            {
                "text": "데이터센터 매출 yoy +110%.",
                "label": "fact",
                "citations": [{"source": "yfinance", "date_ref": "2026Q1"}],
            }
        ],
        "risks": [
            {"text": "ASIC 경쟁 심화로 GPU ASP 압박 가능성.", "label": "opinion", "citations": []}
        ],
        "scenarios": [
            {
                "name": "base",
                "triggers": ["Fwd EPS 컨센 유지"],
                "assumptions": ["Fwd PER 32x"],
                "target_range_low": 900.0,
                "target_range_high": 1050.0,
                "probability_qualitative": "medium",
                "rationale": "현재 멀티플 정합 범위",
            }
        ],
        "data_caveats": ["부문별 OP 미공개"],
    }


def _technical_payload() -> dict[str, Any]:
    return {
        "summary": "정배열 + RSI 62 — 상승 추세 진행 중.",
        "trend": "MA20 > MA50 > MA200 완전 정배열.",
        "moving_averages": {"ma20": 890.0, "ma50": 850.0, "ma200": 700.0},
        "momentum": "RSI 62, 과열 직전.",
        "levels": [
            {"kind": "support", "price": 850.0, "rationale": "MA50 지지대"},
            {"kind": "resistance", "price": 950.0, "rationale": "52w 고점"},
        ],
        "scenarios": [
            {
                "name": "bullish",
                "triggers": ["950 돌파 + 거래량 동반"],
                "assumptions": ["RSI 70 미만 유지"],
                "target_range_low": 980.0,
                "target_range_high": 1050.0,
                "probability_qualitative": "medium",
                "rationale": "전 고점 돌파 시 1차 1,000",
            }
        ],
        "data_caveats": ["기술적 분석은 후행 지표 기반"],
    }


def _make_chat_result(payload: dict[str, Any]) -> ChatResult:
    return ChatResult(
        content=json.dumps(payload),
        model="openai/gpt-oss-120b",
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
    )


def _mock_client(payload: dict[str, Any]) -> OpenRouterClient:
    client = OpenRouterClient.__new__(OpenRouterClient)
    client.client = None  # type: ignore[attr-defined]
    client.settings = None  # type: ignore[attr-defined]
    client.chat = AsyncMock(return_value=_make_chat_result(payload))  # type: ignore[attr-defined]
    return client


async def test_fundamental_agent_parses_valid_json(
    analysis_data: AnalysisData,
) -> None:
    client = _mock_client(_fundamental_payload())
    agent = FundamentalAgent(client=client)
    run = await agent.run(analysis_data)
    assert run.role == "fundamental"
    assert isinstance(run.output, FundamentalOutput)
    assert run.output.summary.startswith("데이터센터")
    assert run.output.scenarios[0].name == "base"
    assert run.total_tokens == 1500
    assert not run.retried


async def test_technical_agent_parses_valid_json(
    analysis_data: AnalysisData,
) -> None:
    client = _mock_client(_technical_payload())
    agent = TechnicalAgent(client=client)
    run = await agent.run(analysis_data)
    assert isinstance(run.output, TechnicalOutput)
    assert run.output.moving_averages["ma20"] == 890.0
    assert run.output.levels[0].kind == "support"


async def test_agent_retries_then_raises_on_persistent_failure(
    analysis_data: AnalysisData,
) -> None:
    bad = ChatResult(content="not json at all", model="openai/gpt-oss-120b")
    client = OpenRouterClient.__new__(OpenRouterClient)
    client.client = None  # type: ignore[attr-defined]
    client.settings = None  # type: ignore[attr-defined]
    client.chat = AsyncMock(return_value=bad)  # type: ignore[attr-defined]
    agent = FundamentalAgent(client=client)

    with pytest.raises(AgentExecutionError):
        await agent.run(analysis_data)
    # Both initial + retry attempted
    assert client.chat.await_count == 2  # type: ignore[attr-defined]


async def test_agent_recovers_on_second_attempt(
    analysis_data: AnalysisData,
) -> None:
    good = _make_chat_result(_fundamental_payload())
    bad = ChatResult(content="oops", model="openai/gpt-oss-120b")
    client = OpenRouterClient.__new__(OpenRouterClient)
    client.client = None  # type: ignore[attr-defined]
    client.settings = None  # type: ignore[attr-defined]
    client.chat = AsyncMock(side_effect=[bad, good])  # type: ignore[attr-defined]
    agent = FundamentalAgent(client=client)
    run = await agent.run(analysis_data)
    assert run.retried is True
    assert run.output.summary.startswith("데이터센터")


async def test_reviewer_emits_markdown_and_stamps_model(
    analysis_data: AnalysisData,
) -> None:
    payload = {
        "final_report_markdown": "# NVDA 분석 보고서\n\n...본문...",
        "discrepancies": [],
        "open_questions": ["부문별 OP 미확보"],
    }
    client = _mock_client(payload)
    agent = ReviewerAgent(client=client)
    fundamental = FundamentalOutput.model_validate(_fundamental_payload())
    technical = TechnicalOutput.model_validate(_technical_payload())
    run = await agent.run(analysis_data, fundamental, technical)
    assert "NVDA" in run.output.final_report_markdown  # type: ignore[union-attr]
    assert run.output.used_model == "openai/gpt-oss-120b"  # type: ignore[union-attr]
