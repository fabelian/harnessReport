"""Asset name → ticker resolution via yfinance metadata."""
from __future__ import annotations

import asyncio
import logging
import re

import yfinance as yf

from app.schemas.data import AssetMeta

logger = logging.getLogger(__name__)

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-]{1,12}$")


class ResolverError(ValueError):
    """Raised when an asset string cannot be resolved to a valid ticker."""


def _looks_like_ticker(asset: str) -> bool:
    return bool(_TICKER_RE.match(asset.strip()))


def _resolve_sync(asset: str) -> AssetMeta:
    """Blocking yfinance call — run via asyncio.to_thread."""
    raw = asset.strip().upper()
    if not raw:
        raise ResolverError("empty asset string")

    candidate = raw if _looks_like_ticker(raw) else raw
    try:
        ticker = yf.Ticker(candidate)
        info = ticker.info or {}
    except Exception as exc:  # pragma: no cover — network failure
        raise ResolverError(f"yfinance lookup failed for '{candidate}': {exc}") from exc

    symbol = info.get("symbol") or candidate
    name = info.get("longName") or info.get("shortName")
    if not name and not info.get("regularMarketPrice"):
        raise ResolverError(f"no metadata found for '{candidate}'")

    return AssetMeta(
        ticker=symbol,
        name=name,
        exchange=info.get("exchange") or info.get("fullExchangeName"),
        currency=info.get("currency"),
        sector=info.get("sector"),
        industry=info.get("industry"),
        market_cap=info.get("marketCap"),
        country=info.get("country"),
    )


async def resolve(asset: str) -> AssetMeta:
    """Resolve a user-supplied asset string to ticker metadata."""
    return await asyncio.to_thread(_resolve_sync, asset)
