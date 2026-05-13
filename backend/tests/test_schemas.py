"""Round-trip and basic validation tests for analysis data schemas."""
from __future__ import annotations

from datetime import date

from app.schemas.data import (
    AnalysisData,
    AssetMeta,
    KeyRatios,
    MacroSnapshot,
    NewsBundle,
    NewsItem,
    PricePoint,
    PriceSeries,
    PriceSummary,
    TechnicalIndicators,
)


def _make_analysis() -> AnalysisData:
    asset = AssetMeta(ticker="NVDA", name="NVIDIA Corporation", currency="USD")
    prices = PriceSeries(
        ticker="NVDA",
        as_of_date=date(2026, 5, 13),
        points=[
            PricePoint(
                date=date(2026, 5, 12),
                open=100.0,
                high=102.0,
                low=99.5,
                close=101.5,
                volume=12_345_678,
            )
        ],
        indicators=TechnicalIndicators(ma20=100.0, rsi14=55.0),
        summary=PriceSummary(as_of_close=101.5, return_1m=0.05),
    )
    news = NewsBundle(
        ticker="NVDA",
        as_of_date=date(2026, 5, 13),
        items=[NewsItem(title="x", url="https://example.com")],
        provider="newsapi",
    )
    macro = MacroSnapshot(as_of_date=date(2026, 5, 13), provider="none")
    return AnalysisData(
        asset=asset,
        as_of_date=date(2026, 5, 13),
        prices=prices,
        news=news,
        macro=macro,
    )


def test_round_trip_json() -> None:
    data = _make_analysis()
    blob = data.model_dump_json()
    restored = AnalysisData.model_validate_json(blob)
    assert restored.asset.ticker == "NVDA"
    assert restored.prices is not None
    assert restored.prices.summary.as_of_close == 101.5
    assert restored.news is not None
    assert restored.news.provider == "newsapi"


def test_summary_helper() -> None:
    data = _make_analysis()
    summary = data.summary()
    assert summary["ticker"] == "NVDA"
    assert summary["price_rows"] == 1
    assert summary["news_count"] == 1
    assert summary["macro_available"] is True
    assert summary["errors"] == []


def test_optional_fields_default() -> None:
    ratios = KeyRatios()
    assert ratios.pe_trailing is None
    assert ratios.payout_ratio is None
