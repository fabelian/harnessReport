"""Verify graceful degradation when external API keys are missing."""
from __future__ import annotations

from datetime import date

import pytest

from app.config import Settings, get_settings
from app.data.macro import fetch_macro
from app.data.news import fetch_news


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure get_settings reads our patched env, not a cached instance."""
    get_settings.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("NEWS_API_KEY", "")
    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("FRED_API_KEY", "")
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]


async def test_news_without_api_keys_returns_empty_bundle() -> None:
    bundle = await fetch_news("NVDA", "NVIDIA", date(2026, 5, 13))
    assert bundle.provider == "none"
    assert bundle.items == []
    assert bundle.note and "NEWS_API_KEY" in bundle.note


async def test_macro_without_fred_key_returns_empty_snapshot() -> None:
    snapshot = await fetch_macro(date(2026, 5, 13))
    assert snapshot.provider == "none"
    assert snapshot.fed_funds_rate is None
    assert snapshot.note and "FRED_API_KEY" in snapshot.note


def test_settings_load_with_empty_keys() -> None:
    settings = Settings()
    assert settings.openrouter_configured is False
    assert settings.openrouter_default_model
