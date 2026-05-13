"""Fetch macro indicators from FRED (Federal Reserve Economic Data)."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from math import isnan

import pandas as pd

from app.config import get_settings
from app.schemas.data import MacroIndicator, MacroSnapshot

logger = logging.getLogger(__name__)

# Series IDs used in the MVP. Labels are human-readable; series_id is FRED-canonical.
SERIES = {
    "fed_funds_rate": ("FEDFUNDS", "Federal Funds Effective Rate (%)"),
    "ust_10y": ("DGS10", "10-Year Treasury Yield (%)"),
    "dxy": ("DTWEXBGS", "Trade-Weighted USD Index (Broad)"),
    "vix": ("VIXCLS", "CBOE Volatility Index"),
}


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if isnan(f):
        return None
    return f


def _build_indicator(series: pd.Series, series_id: str, label: str) -> MacroIndicator:
    series = series.dropna()
    if series.empty:
        return MacroIndicator(
            series_id=series_id, label=label, note="no observations returned"
        )
    latest_value = _safe_float(series.iloc[-1])
    latest_date = pd.Timestamp(series.index[-1]).date()

    def _change(months: int) -> float | None:
        ref_ts = pd.Timestamp(latest_date) - pd.DateOffset(months=months)
        candidates = series[series.index <= ref_ts]
        if candidates.empty or latest_value is None:
            return None
        ref_val = _safe_float(candidates.iloc[-1])
        if ref_val is None:
            return None
        return latest_value - ref_val

    return MacroIndicator(
        series_id=series_id,
        label=label,
        latest_value=latest_value,
        latest_date=latest_date,
        change_3m=_change(3),
        change_6m=_change(6),
    )


def _fetch_sync(api_key: str, as_of_date: date) -> MacroSnapshot:
    from fredapi import Fred  # imported lazily so dev without key still works

    fred = Fred(api_key=api_key)
    start = as_of_date - timedelta(days=400)
    end = as_of_date

    snapshot_kwargs: dict[str, MacroIndicator | None] = {}
    for attr, (series_id, label) in SERIES.items():
        try:
            series = fred.get_series(
                series_id, observation_start=start, observation_end=end
            )
            snapshot_kwargs[attr] = _build_indicator(series, series_id, label)
        except Exception as exc:  # pragma: no cover — network/quota
            logger.warning("FRED fetch failed for %s: %s", series_id, exc)
            snapshot_kwargs[attr] = MacroIndicator(
                series_id=series_id, label=label, note=f"fetch failed: {exc}"
            )

    return MacroSnapshot(
        as_of_date=as_of_date,
        provider="fred",
        **snapshot_kwargs,  # type: ignore[arg-type]
    )


async def fetch_macro(as_of_date: date) -> MacroSnapshot:
    """Fetch macro snapshot. If FRED_API_KEY is missing, returns an empty snapshot."""
    settings = get_settings()
    if not settings.fred_api_key:
        return MacroSnapshot(
            as_of_date=as_of_date,
            provider="none",
            note="FRED_API_KEY not configured — macro indicators unavailable",
        )
    return await asyncio.to_thread(_fetch_sync, settings.fred_api_key, as_of_date)
