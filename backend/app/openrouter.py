"""OpenRouter API client.

Thin wrapper around the OpenAI SDK pointed at the OpenRouter endpoint.
Provides:

- `chat()` — single-shot chat completion, optional JSON response_format
- `chat_stream()` — async iterator over content deltas
- `echo_test()` — minimal connectivity check for `/api/health` or scripts

All calls are retried on transient errors (429 / 5xx / network) with bounded
exponential backoff via `tenacity`.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChatResult:
    """Result of a single chat completion call."""

    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None
    raw: Any = None


class OpenRouterError(RuntimeError):
    """Raised when OpenRouter call fails after retries or returns invalid data."""


class OpenRouterClient:
    """Async OpenRouter client backed by the OpenAI SDK."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.openrouter_api_key:
            logger.warning(
                "OPENROUTER_API_KEY is empty; chat calls will fail until configured"
            )
        self._client = AsyncOpenAI(
            api_key=self.settings.openrouter_api_key or "missing-key",
            base_url=self.settings.openrouter_base_url,
            default_headers={
                # OpenRouter recommends these headers for app identification.
                "HTTP-Referer": "https://github.com/fabelian/harnessReport",
                "X-Title": "Equity Research Harness",
            },
            timeout=120.0,
        )

    @property
    def default_model(self) -> str:
        return self.settings.openrouter_default_model

    def _retryer(self) -> AsyncRetrying:
        return AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=20),
            retry=retry_if_exception_type(
                (RateLimitError, APIConnectionError, APIError)
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

    async def chat(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        json_mode: bool = False,
        json_schema: dict | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> ChatResult:
        """Single-shot chat completion."""
        chosen_model = model or self.default_model
        kwargs: dict[str, Any] = {
            "model": chosen_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": json_schema,
            }
        elif json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            async for attempt in self._retryer():
                with attempt:
                    response = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # pragma: no cover — network failures
            raise OpenRouterError(f"chat failed: {exc}") from exc

        if not response.choices:
            raise OpenRouterError("empty choices in OpenRouter response")
        choice = response.choices[0]
        content = choice.message.content or ""
        usage = response.usage
        return ChatResult(
            content=content,
            model=response.model or chosen_model,
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            total_tokens=getattr(usage, "total_tokens", None) if usage else None,
            finish_reason=choice.finish_reason,
            raw=response,
        )

    async def chat_stream(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream content deltas. Yields plain text chunks."""
        chosen_model = model or self.default_model
        try:
            stream = await self._client.chat.completions.create(
                model=chosen_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
        except Exception as exc:  # pragma: no cover
            raise OpenRouterError(f"stream open failed: {exc}") from exc

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = getattr(delta, "content", None)
            if piece:
                yield piece

    async def echo_test(self, model: str | None = None) -> ChatResult:
        """Minimal connectivity check — ask the model to say 'pong'."""
        return await self.chat(
            system="You are a connectivity probe. Reply with exactly the single word: pong",
            user="ping",
            model=model,
            temperature=0.0,
            max_tokens=16,
        )

    async def close(self) -> None:
        await self._client.close()


# Convenience module-level singleton (lazy)
_client_instance: OpenRouterClient | None = None


def get_client() -> OpenRouterClient:
    """Return a shared client instance.

    If `OPENROUTER_API_KEY == "demo"`, returns a `DemoOpenRouterClient` that
    serves canned responses — useful for UI development / first-time setup
    without an OpenRouter account.
    """
    global _client_instance
    if _client_instance is None:
        settings = get_settings()
        if settings.openrouter_api_key.lower() == "demo":
            from app.openrouter_demo import DemoOpenRouterClient  # local import

            logger.warning("OpenRouter DEMO mode active — responses are canned")
            _client_instance = DemoOpenRouterClient(  # type: ignore[assignment]
                default_model=settings.openrouter_default_model
            )
        else:
            _client_instance = OpenRouterClient()
    return _client_instance


def reset_client() -> None:
    """Clear the cached client (used in tests)."""
    global _client_instance
    _client_instance = None
