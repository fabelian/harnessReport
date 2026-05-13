"""Integration test for fetcher orchestration with mocked sources."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

from app.data.fetcher import fetch_all
from app.schemas.data import (
    AssetMeta,
    Fundamentals,
    KeyRatios,
    MacroSnapshot,
    NewsBundle,
    PriceSeries,
    PriceSummary,
    TechnicalIndicators,
)


def _meta() -> AssetMeta:
    return AssetMeta(ticker="NVDA", name="NVIDIA", currency="USD")


def _prices() -> PriceSeries:
    return PriceSeries(
        ticker="NVDA",
        as_of_date=date(2026, 5, 13),
        points=[],
        indicators=TechnicalIndicators(),
        summary=PriceSummary(as_of_close=900.0),
    )


def _fundamentals() -> Fundamentals:
    return Fundamentals(
        ticker="NVDA",
        as_of_date=date(2026, 5, 13),
        ratios=KeyRatios(pe_trailing=50.0),
    )


async def test_fetch_all_aggregates_sources() -> None:
    progress_events: list[tuple[str, str]] = []

    with (
        patch("app.data.fetcher.resolve", new=AsyncMock(return_value=_meta())),
        patch("app.data.fetcher.fetch_prices", new=AsyncMock(return_value=_prices())),
        patch(
            "app.data.fetcher.fetch_fundamentals",
            new=AsyncMock(return_value=_fundamentals()),
        ),
        patch(
            "app.data.fetcher.fetch_news",
            new=AsyncMock(
                return_value=NewsBundle(
                    ticker="NVDA",
                    as_of_date=date(2026, 5, 13),
                    items=[],
                    provider="none",
                )
            ),
        ),
        patch(
            "app.data.fetcher.fetch_macro",
            new=AsyncMock(
                return_value=MacroSnapshot(
                    as_of_date=date(2026, 5, 13), provider="none"
                )
            ),
        ),
    ):
        result = await fetch_all(
            "NVDA",
            date(2026, 5, 13),
            on_progress=lambda source, status: progress_events.append((source, status)),
        )

    assert result.asset.ticker == "NVDA"
    assert result.prices is not None
    assert result.fundamentals is not None
    assert result.news is not None
    assert result.macro is not None
    assert result.errors == []

    # Progress events fired for every source (start + done)
    sources_seen = {evt[0] for evt in progress_events}
    assert sources_seen >= {"resolver", "prices", "fundamentals", "news", "macro"}


async def test_fetch_all_records_partial_failure() -> None:
    async def _boom(*args, **kwargs):
        raise RuntimeError("yfinance down")

    with (
        patch("app.data.fetcher.resolve", new=AsyncMock(return_value=_meta())),
        patch("app.data.fetcher.fetch_prices", new=AsyncMock(side_effect=_boom)),
        patch(
            "app.data.fetcher.fetch_fundamentals",
            new=AsyncMock(return_value=_fundamentals()),
        ),
        patch(
            "app.data.fetcher.fetch_news",
            new=AsyncMock(
                return_value=NewsBundle(
                    ticker="NVDA",
                    as_of_date=date(2026, 5, 13),
                    items=[],
                    provider="none",
                )
            ),
        ),
        patch(
            "app.data.fetcher.fetch_macro",
            new=AsyncMock(
                return_value=MacroSnapshot(
                    as_of_date=date(2026, 5, 13), provider="none"
                )
            ),
        ),
    ):
        result = await fetch_all("NVDA", date(2026, 5, 13))

    assert result.prices is None
    assert result.fundamentals is not None
    assert any("prices" in err for err in result.errors)
