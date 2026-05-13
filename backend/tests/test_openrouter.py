"""Structural tests for the OpenRouter wrapper (no network)."""
from __future__ import annotations

import pytest

from app.config import get_settings
from app.openrouter import ChatResult, OpenRouterClient


@pytest.fixture(autouse=True)
def _stub_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-oss-120b")
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_client_initialises_with_settings() -> None:
    client = OpenRouterClient()
    assert client.default_model == "openai/gpt-oss-120b"
    assert client.settings.openrouter_api_key == "test-key"


def test_chat_result_dataclass_defaults() -> None:
    result = ChatResult(content="hello", model="x")
    assert result.content == "hello"
    assert result.model == "x"
    assert result.prompt_tokens is None
    assert result.total_tokens is None
