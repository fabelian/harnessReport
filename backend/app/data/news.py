"""Fetch recent news headlines via NewsAPI or Tavily.

Falls back to an empty bundle (with a `note`) when neither API key is configured
so the pipeline continues to produce a report.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

from app.config import get_settings
from app.schemas.data import NewsBundle, NewsItem

logger = logging.getLogger(__name__)


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


async def _fetch_newsapi(
    query: str, as_of_date: date, *, api_key: str, days: int, limit: int
) -> NewsBundle:
    from_date = (as_of_date - timedelta(days=days)).isoformat()
    to_date = as_of_date.isoformat()
    params = {
        "q": query,
        "from": from_date,
        "to": to_date,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": min(limit, 100),
    }
    headers = {"X-Api-Key": api_key}
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.get(
            "https://newsapi.org/v2/everything", params=params, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()

    items: list[NewsItem] = []
    for art in data.get("articles", [])[:limit]:
        items.append(
            NewsItem(
                title=art.get("title") or "",
                source=(art.get("source") or {}).get("name"),
                url=art.get("url"),
                published_at=_parse_date(art.get("publishedAt")),
                summary=art.get("description"),
            )
        )
    return NewsBundle(
        ticker=query,
        as_of_date=as_of_date,
        items=items,
        provider="newsapi",
    )


async def _fetch_tavily(
    query: str, as_of_date: date, *, api_key: str, days: int, limit: int
) -> NewsBundle:
    payload = {
        "api_key": api_key,
        "query": f"{query} stock news",
        "search_depth": "basic",
        "topic": "news",
        "days": days,
        "max_results": min(limit, 20),
        "include_answer": False,
        "include_raw_content": False,
    }
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post("https://api.tavily.com/search", json=payload)
        resp.raise_for_status()
        data = resp.json()

    items: list[NewsItem] = []
    for res in data.get("results", [])[:limit]:
        items.append(
            NewsItem(
                title=res.get("title") or "",
                source=None,
                url=res.get("url"),
                published_at=_parse_date(res.get("published_date")),
                summary=res.get("content"),
            )
        )
    return NewsBundle(
        ticker=query,
        as_of_date=as_of_date,
        items=items,
        provider="tavily",
    )


async def fetch_news(
    ticker: str,
    asset_name: str | None,
    as_of_date: date,
    *,
    days: int = 30,
    limit: int = 20,
) -> NewsBundle:
    """Fetch recent news. Prefers NewsAPI, then Tavily, else empty bundle."""
    settings = get_settings()
    query = asset_name or ticker

    if settings.news_api_key:
        try:
            return await _fetch_newsapi(
                query, as_of_date, api_key=settings.news_api_key, days=days, limit=limit
            )
        except Exception as exc:  # pragma: no cover — network/quota
            logger.warning("NewsAPI failed (%s); falling back", exc)

    if settings.tavily_api_key:
        try:
            return await _fetch_tavily(
                query, as_of_date, api_key=settings.tavily_api_key, days=days, limit=limit
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Tavily failed (%s); falling back", exc)

    return NewsBundle(
        ticker=ticker,
        as_of_date=as_of_date,
        items=[],
        provider="none",
        note="no NEWS_API_KEY or TAVILY_API_KEY configured",
    )
