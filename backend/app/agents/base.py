"""Base class for analyst agents.

Each concrete agent declares:
- `role`, `output_schema`, `system_prompt_path`, `methodology_paths`
- a `build_user_prompt(...)` method that turns inputs into a single string

The shared `_call_and_parse` helper invokes OpenRouter in JSON mode, parses
the response tolerantly, and validates it against `output_schema`. One retry
is attempted on schema-validation failure with a stricter follow-up prompt.
"""
from __future__ import annotations

import json
import logging
from abc import ABC
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.openrouter import ChatResult, OpenRouterClient, get_client
from app.utils.markdown import safe_json_loads
from app.utils.prompt_loader import compose

logger = logging.getLogger(__name__)


class AgentExecutionError(RuntimeError):
    """Raised when an agent cannot produce a valid output after retries."""


@dataclass(slots=True)
class AgentRun:
    """Result of a single agent invocation, including bookkeeping."""

    role: str
    output: BaseModel
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    retried: bool = False


class BaseAgent(ABC):
    role: str = "base"
    output_schema: type[BaseModel]
    system_prompt_path: str
    methodology_paths: tuple[str, ...] = ()

    # Default sampling — agents tend to be deterministic / low-creativity
    default_temperature: float = 0.2
    default_max_tokens: int = 4096

    def __init__(self, client: OpenRouterClient | None = None) -> None:
        self.client = client or get_client()

    # -- prompt assembly ------------------------------------------------------

    def system_prompt(self) -> str:
        return compose(self.system_prompt_path, *self.methodology_paths)

    # subclasses override
    def build_user_prompt(self, **kwargs: Any) -> str:  # pragma: no cover
        raise NotImplementedError

    # -- core call ------------------------------------------------------------

    async def _call_and_parse(
        self,
        *,
        user_prompt: str,
        model: str | None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[BaseModel, ChatResult, bool]:
        """Invoke OpenRouter, parse JSON, validate against `output_schema`.

        Returns `(validated_output, raw_chat_result, retried)`.
        """
        system = self.system_prompt()
        retried = False
        result = await self.client.chat(
            system=system,
            user=user_prompt,
            model=model,
            json_mode=True,
            temperature=temperature or self.default_temperature,
            max_tokens=max_tokens or self.default_max_tokens,
        )

        prior_error: str | None = None
        try:
            parsed_raw = safe_json_loads(result.content)
            output = self.output_schema.model_validate(parsed_raw)
            return output, result, retried
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "agent[%s] parse/validation failed (%s) — retrying once",
                self.role,
                type(exc).__name__,
            )
            retried = True
            prior_error = f"{type(exc).__name__}: {exc}"

        retry_user = (
            user_prompt
            + "\n\n---\nIMPORTANT: Your previous response did not pass JSON validation."
            " Return a single JSON object that matches the schema exactly."
            " No commentary, no markdown fences. Use null for unknown numbers."
            f"\nPrior error: {prior_error}\n"
        )
        result2 = await self.client.chat(
            system=system,
            user=retry_user,
            model=model,
            json_mode=True,
            temperature=0.0,
            max_tokens=max_tokens or self.default_max_tokens,
        )
        try:
            parsed_raw2 = safe_json_loads(result2.content)
            output = self.output_schema.model_validate(parsed_raw2)
            return output, result2, retried
        except (json.JSONDecodeError, ValidationError) as exc2:
            raise AgentExecutionError(
                f"{self.role}: invalid JSON output after 1 retry — {exc2}"
            ) from exc2

    @staticmethod
    def _build_run(role: str, output: BaseModel, result: ChatResult, retried: bool) -> AgentRun:
        return AgentRun(
            role=role,
            output=output,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            retried=retried,
        )
