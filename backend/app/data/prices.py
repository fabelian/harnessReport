"""Fetch OHLCV history via yfinance and compute technical indicators."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from math import isnan

import pandas as pd
import yfinance as yf

from app.data import indicators
from app.schemas.data import (
    PricePoint,
    PriceSeries,
    PriceSummary,
    TechnicalIndicators,
)

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_DAYS = 400  # ~13 months, enough for MA200


def _safe_float(value: object) -> float | None:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if isnan(f):
        return None
    return f


def _compute_indicators(df: pd.DataFrame) -> TechnicalIndicators:
    close = df["Close"]
    ma20 = indicators.sma(close, 20)
    ma50 = indicators.sma(close, 50)
    ma200 = indicators.sma(close, 200)
    rsi14 = indicators.rsi(close, 14)
    macd_line, macd_signal, macd_hist = indicators.macd(close)
    bb_u, bb_m, bb_l = indicators.bollinger(close)
    atr14 = indicators.atr(df, 14)

    return TechnicalIndicators(
        ma20=_safe_float(ma20.iloc[-1]),
        ma50=_safe_float(ma50.iloc[-1]),
        ma200=_safe_float(ma200.iloc[-1]),
        rsi14=_safe_float(rsi14.iloc[-1]),
        macd=_safe_float(macd_line.iloc[-1]),
        macd_signal=_safe_float(macd_signal.iloc[-1]),
        macd_hist=_safe_float(macd_hist.iloc[-1]),
        bb_upper=_safe_float(bb_u.iloc[-1]),
        bb_middle=_safe_float(bb_m.iloc[-1]),
        bb_lower=_safe_float(bb_l.iloc[-1]),
        atr14=_safe_float(atr14.iloc[-1]),
    )


def _compute_summary(df: pd.DataFrame, as_of_date: date) -> PriceSummary:
    close = df["Close"]
    last_close = float(close.iloc[-1])

    def _ret(days: int) -> float | None:
        if len(close) <= days:
            return None
        ref = float(close.iloc[-1 - days])
        if ref == 0:
            return None
        return (last_close / ref) - 1.0

    # YTD return — find first trading day of current year within series
    year_start = pd.Timestamp(year=as_of_date.year, month=1, day=1)
    ytd_slice = close[close.index >= year_start]
    ytd = (
        (last_close / float(ytd_slice.iloc[0])) - 1.0
        if len(ytd_slice) > 0 and float(ytd_slice.iloc[0]) != 0
        else None
    )

    high_52 = float(close.tail(252).max()) if len(close) >= 1 else None
    low_52 = float(close.tail(252).min()) if len(close) >= 1 else None
    avg_vol = float(df["Volume"].tail(30).mean()) if "Volume" in df else None

    return PriceSummary(
        as_of_close=last_close,
        period_high_52w=high_52,
        period_low_52w=low_52,
        return_1m=_ret(21),
        return_3m=_ret(63),
        return_6m=_ret(126),
        return_ytd=ytd,
        return_1y=_ret(252),
        avg_volume_30d=avg_vol,
    )


def _df_to_points(df: pd.DataFrame, limit: int = 90) -> list[PricePoint]:
    """Return only the most recent `limit` rows to keep prompt context small."""
    tail = df.tail(limit)
    points: list[PricePoint] = []
    for ts, row in tail.iterrows():
        try:
            points.append(
                PricePoint(
                    date=pd.Timestamp(ts).date(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                )
            )
        except (KeyError, ValueError):
            continue
    return points


def _fetch_sync(ticker: str, as_of_date: date) -> pd.DataFrame:
    start = as_of_date - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    end = as_of_date + timedelta(days=1)  # yfinance end is exclusive
    df = yf.Ticker(ticker).history(
        start=start.isoformat(),
        end=end.isoformat(),
        interval="1d",
        auto_adjust=False,
        actions=False,
    )
    if df.empty:
        raise ValueError(f"yfinance returned empty history for {ticker}")
    df = df.dropna(subset=["Close"])
    # yfinance returns a tz-aware DatetimeIndex for non-US exchanges (e.g.
    # 000660.KS comes back as Asia/Seoul), which then can't be compared against
    # the tz-naive Timestamp used for the YTD slice in _compute_summary. Daily
    # OHLCV is date-grained, so drop the timezone here as the single point of
    # normalization and let downstream code assume naive timestamps.
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


async def fetch_prices(ticker: str, as_of_date: date) -> PriceSeries:
    """Fetch OHLCV and compute indicators+summary. Returns a `PriceSeries`."""
    df = await asyncio.to_thread(_fetch_sync, ticker, as_of_date)
    series = PriceSeries(
        ticker=ticker,
        as_of_date=as_of_date,
        points=_df_to_points(df, limit=90),
        indicators=_compute_indicators(df),
        summary=_compute_summary(df, as_of_date),
        note=None if len(df) >= 200 else f"only {len(df)} rows available (MA200 unreliable)",
    )
    return series
