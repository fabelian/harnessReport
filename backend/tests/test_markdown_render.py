"""Render `AnalysisData` to markdown and check the produced sections."""
from __future__ import annotations

from datetime import date

from app.schemas.data import (
    AnalysisData,
    AssetMeta,
    FinancialRow,
    Fundamentals,
    KeyRatios,
    MacroIndicator,
    MacroSnapshot,
    NewsBundle,
    NewsItem,
    PricePoint,
    PriceSeries,
    PriceSummary,
    TechnicalIndicators,
)
from app.utils.markdown import render_full_context, safe_json_loads


def _data() -> AnalysisData:
    return AnalysisData(
        asset=AssetMeta(
            ticker="NVDA",
            name="NVIDIA Corp",
            exchange="NASDAQ",
            currency="USD",
            market_cap=2.5e12,
        ),
        as_of_date=date(2026, 5, 13),
        prices=PriceSeries(
            ticker="NVDA",
            as_of_date=date(2026, 5, 13),
            points=[
                PricePoint(
                    date=date(2026, 5, 12),
                    open=900.0,
                    high=910.0,
                    low=890.0,
                    close=905.0,
                    volume=12_345_678,
                ),
            ],
            indicators=TechnicalIndicators(ma20=890.0, rsi14=62.0),
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
                    revenue=44e9,
                    operating_income=29e9,
                    net_income=24e9,
                    eps=0.95,
                    op_margin=0.66,
                )
            ],
            ratios=KeyRatios(pe_trailing=55.0, pe_forward=32.0),
            cash=10e9,
            total_debt=8e9,
        ),
        news=NewsBundle(
            ticker="NVDA",
            as_of_date=date(2026, 5, 13),
            items=[
                NewsItem(
                    title="Quarter beats estimates",
                    source="Reuters",
                    url="https://example.com/x",
                    published_at=date(2026, 5, 10),
                )
            ],
            provider="newsapi",
        ),
        macro=MacroSnapshot(
            as_of_date=date(2026, 5, 13),
            provider="fred",
            fed_funds_rate=MacroIndicator(
                series_id="FEDFUNDS",
                label="Federal Funds Effective Rate (%)",
                latest_value=4.5,
                latest_date=date(2026, 4, 30),
                change_3m=-0.25,
            ),
        ),
    )


def test_render_full_context_contains_each_section() -> None:
    text = render_full_context(_data())
    assert "# Analysis Context" in text
    assert "## Asset Metadata" in text
    assert "## Price Series" in text
    assert "## Fundamentals" in text
    assert "## Recent News" in text
    assert "## Macro Snapshot" in text
    # Spot-check numbers actually render
    assert "905" in text  # close
    assert "62.00" in text  # rsi
    assert "2026Q1" in text
    assert "Reuters" in text
    assert "Federal Funds" in text


def test_safe_json_loads_strips_code_fences() -> None:
    text = "```json\n{\"a\": 1}\n```"
    assert safe_json_loads(text) == {"a": 1}


def test_safe_json_loads_plain_json() -> None:
    text = '{"foo": [1, 2, 3]}'
    assert safe_json_loads(text)["foo"] == [1, 2, 3]
