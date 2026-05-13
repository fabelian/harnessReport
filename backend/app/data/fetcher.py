"""Top-level data fetcher — runs all sources in parallel and assembles `AnalysisData`.

Each source is wrapped so that a single failure (e.g. NewsAPI down) does not
abort the whole pipeline; the failure is recorded under `AnalysisData.errors`
and the corresponding field is left `None` so downstream agents can note it.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date
from typing import TypeVar

from app.data.fundamentals import fetch_fundamentals
from app.data.macro import fetch_macro
from app.data.news import fetch_news
from app.data.prices import fetch_prices
from app.data.resolver import resolve
from app.schemas.data import (
    AnalysisData,
    AssetMeta,
    Fundamentals,
    MacroSnapshot,
    NewsBundle,
    PriceSeries,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def _safe(
    label: str, coro: Awaitable[T], errors: list[str]
) -> T | None:
    """Run a coroutine; on exception log + append to errors and return None."""
    try:
        return await coro
    except Exception as exc:
        logger.warning("data fetch failed: %s — %s", label, exc)
        errors.append(f"{label}: {exc}")
        return None


async def fetch_all(
    asset: str,
    as_of_date: date,
    *,
    on_progress: Callable[[str, str], None] | None = None,
) -> AnalysisData:
    """Resolve the asset and fetch prices/fundamentals/news/macro in parallel.

    `on_progress(source, status)` is invoked at start and completion of each
    source so callers (e.g. SSE orchestrator) can stream progress events.
    """
    errors: list[str] = []

    if on_progress:
        on_progress("resolver", "start")
    meta: AssetMeta = await resolve(asset)
    if on_progress:
        on_progress("resolver", "done")

    async def _wrap(label: str, coro: Awaitable[T]) -> T | None:
        if on_progress:
            on_progress(label, "start")
        result = await _safe(label, coro, errors)
        if on_progress:
            on_progress(label, "done" if result is not None else "error")
        return result

    prices_task = _wrap("prices", fetch_prices(meta.ticker, as_of_date))
    fundamentals_task = _wrap(
        "fundamentals", fetch_fundamentals(meta.ticker, as_of_date)
    )
    news_task = _wrap("news", fetch_news(meta.ticker, meta.name, as_of_date))
    macro_task = _wrap("macro", fetch_macro(as_of_date))

    prices, fundamentals, news, macro = await asyncio.gather(
        prices_task, fundamentals_task, news_task, macro_task
    )

    return AnalysisData(
        asset=meta,
        as_of_date=as_of_date,
        prices=prices,  # type: ignore[arg-type]
        fundamentals=fundamentals,  # type: ignore[arg-type]
        news=news,  # type: ignore[arg-type]
        macro=macro,  # type: ignore[arg-type]
        errors=errors,
    )
