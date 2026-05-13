"""Data containers for analysis inputs (fetched data passed to agents)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AssetMeta(BaseModel):
    """Resolved metadata for an asset (ticker, name, exchange, currency)."""

    ticker: str
    name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    country: str | None = None


class PricePoint(BaseModel):
    """A single OHLCV bar."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class TechnicalIndicators(BaseModel):
    """Latest indicator values computed on the price series."""

    ma20: float | None = None
    ma50: float | None = None
    ma200: float | None = None
    rsi14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    atr14: float | None = None


class PriceSummary(BaseModel):
    """Convenience summary statistics across the series."""

    as_of_close: float
    period_high_52w: float | None = None
    period_low_52w: float | None = None
    return_1m: float | None = None
    return_3m: float | None = None
    return_6m: float | None = None
    return_ytd: float | None = None
    return_1y: float | None = None
    avg_volume_30d: float | None = None


class PriceSeries(BaseModel):
    """OHLCV series + computed indicators + summary."""

    ticker: str
    as_of_date: date
    points: list[PricePoint] = Field(default_factory=list)
    indicators: TechnicalIndicators
    summary: PriceSummary
    note: str | None = None  # data caveat, e.g. "partial series"


class FinancialRow(BaseModel):
    """A single quarter (or annual) financial line."""

    period: str  # e.g. "2025Q4" or "FY2024"
    revenue: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    eps: float | None = None
    op_margin: float | None = None
    net_margin: float | None = None


class KeyRatios(BaseModel):
    """Latest valuation / efficiency ratios from yfinance info."""

    pe_trailing: float | None = None
    pe_forward: float | None = None
    pb: float | None = None
    ev_ebitda: float | None = None
    ev_sales: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    dividend_yield: float | None = None
    payout_ratio: float | None = None


class Fundamentals(BaseModel):
    """Per-asset fundamental snapshot."""

    ticker: str
    as_of_date: date
    quarters: list[FinancialRow] = Field(default_factory=list)
    annuals: list[FinancialRow] = Field(default_factory=list)
    ratios: KeyRatios
    cash: float | None = None
    total_debt: float | None = None
    note: str | None = None


class NewsItem(BaseModel):
    """A single news headline / summary."""

    title: str
    source: str | None = None
    url: str | None = None
    published_at: date | None = None
    summary: str | None = None


class NewsBundle(BaseModel):
    """Collection of recent news + provider note."""

    ticker: str
    as_of_date: date
    items: list[NewsItem] = Field(default_factory=list)
    provider: str  # "newsapi" | "tavily" | "none"
    note: str | None = None


class MacroIndicator(BaseModel):
    """Latest value + small recent history for a single macro series."""

    series_id: str
    label: str
    latest_value: float | None = None
    latest_date: date | None = None
    change_3m: float | None = None  # absolute change vs 3 months ago
    change_6m: float | None = None
    note: str | None = None


class MacroSnapshot(BaseModel):
    """Bundle of macro indicators relevant to equity analysis."""

    as_of_date: date
    fed_funds_rate: MacroIndicator | None = None
    ust_10y: MacroIndicator | None = None
    dxy: MacroIndicator | None = None
    vix: MacroIndicator | None = None
    provider: str  # "fred" | "none"
    note: str | None = None


class AnalysisData(BaseModel):
    """Top-level container passed to every agent."""

    model_config = ConfigDict(arbitrary_types_allowed=False)

    asset: AssetMeta
    as_of_date: date
    prices: PriceSeries | None = None
    fundamentals: Fundamentals | None = None
    news: NewsBundle | None = None
    macro: MacroSnapshot | None = None
    errors: list[str] = Field(default_factory=list)

    def summary(self) -> dict:
        """Concise diagnostic summary for SSE events / logs."""
        return {
            "ticker": self.asset.ticker,
            "as_of_date": self.as_of_date.isoformat(),
            "price_rows": len(self.prices.points) if self.prices else 0,
            "quarters": len(self.fundamentals.quarters) if self.fundamentals else 0,
            "news_count": len(self.news.items) if self.news else 0,
            "macro_available": self.macro is not None,
            "errors": self.errors,
        }


# Forward reference for explicit export
__all__ = [
    "AssetMeta",
    "PricePoint",
    "TechnicalIndicators",
    "PriceSummary",
    "PriceSeries",
    "FinancialRow",
    "KeyRatios",
    "Fundamentals",
    "NewsItem",
    "NewsBundle",
    "MacroIndicator",
    "MacroSnapshot",
    "AnalysisData",
]
