"""Fetch fundamental financial data via yfinance."""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from math import isnan

import pandas as pd
import yfinance as yf

from app.schemas.data import FinancialRow, Fundamentals, KeyRatios

logger = logging.getLogger(__name__)


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


def _row_value(df: pd.DataFrame, row_name: str, col: pd.Timestamp) -> float | None:
    """Look up a value with row-name fallbacks (yfinance label variants)."""
    if df is None or df.empty:
        return None
    # Try exact, then case-insensitive partial match
    if row_name in df.index:
        val = df.at[row_name, col]
        return _safe_float(val)
    candidates = [idx for idx in df.index if row_name.lower() in str(idx).lower()]
    if candidates:
        return _safe_float(df.at[candidates[0], col])
    return None


def _period_label(ts: pd.Timestamp, *, annual: bool) -> str:
    if annual:
        return f"FY{ts.year}"
    quarter = (ts.month - 1) // 3 + 1
    return f"{ts.year}Q{quarter}"


def _rows_from_financials(
    income: pd.DataFrame, *, annual: bool, limit: int = 4
) -> list[FinancialRow]:
    if income is None or income.empty:
        return []
    rows: list[FinancialRow] = []
    cols = list(income.columns)[:limit]
    for col in cols:
        revenue = _row_value(income, "Total Revenue", col) or _row_value(
            income, "Revenue", col
        )
        op_income = _row_value(income, "Operating Income", col)
        net_income = _row_value(income, "Net Income", col)
        eps = _row_value(income, "Basic EPS", col) or _row_value(income, "Diluted EPS", col)
        op_margin = (op_income / revenue) if revenue and op_income else None
        net_margin = (net_income / revenue) if revenue and net_income else None
        rows.append(
            FinancialRow(
                period=_period_label(pd.Timestamp(col), annual=annual),
                revenue=revenue,
                operating_income=op_income,
                net_income=net_income,
                eps=eps,
                op_margin=op_margin,
                net_margin=net_margin,
            )
        )
    return rows


def _ratios_from_info(info: dict) -> KeyRatios:
    return KeyRatios(
        pe_trailing=_safe_float(info.get("trailingPE")),
        pe_forward=_safe_float(info.get("forwardPE")),
        pb=_safe_float(info.get("priceToBook")),
        ev_ebitda=_safe_float(info.get("enterpriseToEbitda")),
        ev_sales=_safe_float(info.get("enterpriseToRevenue")),
        roe=_safe_float(info.get("returnOnEquity")),
        debt_to_equity=_safe_float(info.get("debtToEquity")),
        current_ratio=_safe_float(info.get("currentRatio")),
        dividend_yield=_safe_float(info.get("dividendYield")),
        payout_ratio=_safe_float(info.get("payoutRatio")),
    )


def _balance_snapshot(balance: pd.DataFrame) -> tuple[float | None, float | None]:
    if balance is None or balance.empty:
        return None, None
    col = balance.columns[0]
    cash = _row_value(balance, "Cash And Cash Equivalents", col) or _row_value(
        balance, "Cash", col
    )
    total_debt = _row_value(balance, "Total Debt", col)
    if total_debt is None:
        # Sum long-term + short-term debt if available
        lt = _row_value(balance, "Long Term Debt", col) or 0.0
        st = _row_value(balance, "Short Long Term Debt", col) or _row_value(
            balance, "Current Debt", col
        ) or 0.0
        total_debt = (lt + st) if (lt or st) else None
    return cash, total_debt


def _fetch_sync(ticker: str, as_of_date: date) -> Fundamentals:
    yticker = yf.Ticker(ticker)
    try:
        info = yticker.info or {}
    except Exception as exc:  # pragma: no cover
        logger.warning("yfinance info fetch failed for %s: %s", ticker, exc)
        info = {}

    try:
        q_income = yticker.quarterly_financials  # type: ignore[assignment]
    except Exception:  # pragma: no cover
        q_income = pd.DataFrame()
    try:
        a_income = yticker.financials  # type: ignore[assignment]
    except Exception:  # pragma: no cover
        a_income = pd.DataFrame()
    try:
        q_balance = yticker.quarterly_balance_sheet  # type: ignore[assignment]
    except Exception:  # pragma: no cover
        q_balance = pd.DataFrame()

    quarters = _rows_from_financials(q_income, annual=False, limit=4)
    annuals = _rows_from_financials(a_income, annual=True, limit=3)
    cash, total_debt = _balance_snapshot(q_balance)

    note = None
    if not quarters and not annuals:
        note = "financial statements unavailable from yfinance"

    return Fundamentals(
        ticker=ticker,
        as_of_date=as_of_date,
        quarters=quarters,
        annuals=annuals,
        ratios=_ratios_from_info(info),
        cash=cash,
        total_debt=total_debt,
        note=note,
    )


async def fetch_fundamentals(ticker: str, as_of_date: date) -> Fundamentals:
    return await asyncio.to_thread(_fetch_sync, ticker, as_of_date)
