"""Sanity tests for indicator calculations on synthetic price series."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.data import indicators


def _make_df(close: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=len(close), freq="B")
    return pd.DataFrame(
        {
            "Open": close,
            "High": [c * 1.01 for c in close],
            "Low": [c * 0.99 for c in close],
            "Close": close,
            "Volume": [1000] * len(close),
        },
        index=idx,
    )


def test_sma_matches_simple_average() -> None:
    df = _make_df(list(range(1, 31)))  # 1..30
    sma5 = indicators.sma(df["Close"], 5)
    # Last 5-window mean of (26..30) == 28
    assert sma5.iloc[-1] == 28.0
    # First 4 values are NaN
    assert sma5.iloc[:4].isna().all()


def test_rsi_extremes_on_monotonic_series() -> None:
    rising = _make_df([float(x) for x in range(1, 50)])
    rsi = indicators.rsi(rising["Close"], 14).dropna()
    # Monotonic rise → RSI saturates near 100
    assert rsi.iloc[-1] > 90.0

    falling = _make_df([float(x) for x in range(50, 1, -1)])
    rsi_down = indicators.rsi(falling["Close"], 14).dropna()
    assert rsi_down.iloc[-1] < 10.0


def test_macd_zero_on_flat_series() -> None:
    df = _make_df([100.0] * 50)
    macd, signal, hist = indicators.macd(df["Close"])
    assert abs(macd.iloc[-1]) < 1e-9
    assert abs(signal.iloc[-1]) < 1e-9
    assert abs(hist.iloc[-1]) < 1e-9


def test_bollinger_band_widths_positive() -> None:
    rng = np.random.default_rng(seed=42)
    closes = (100 + rng.normal(0, 2.0, 80)).tolist()
    df = _make_df(closes)
    upper, mid, lower = indicators.bollinger(df["Close"])
    last_u = upper.iloc[-1]
    last_l = lower.iloc[-1]
    last_m = mid.iloc[-1]
    assert last_u > last_m > last_l
    assert (last_u - last_l) > 0


def test_atr_positive_on_volatile_series() -> None:
    rng = np.random.default_rng(seed=1)
    closes = (100 + rng.normal(0, 3.0, 60)).tolist()
    df = _make_df(closes)
    a = indicators.atr(df, 14).dropna()
    assert a.iloc[-1] > 0
