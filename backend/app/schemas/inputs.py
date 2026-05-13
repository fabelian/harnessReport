"""Request schemas for the public API."""
from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelChoice(str, Enum):
    """User-selectable OpenRouter model IDs.

    Add new entries here when the OpenRouter catalog changes; the frontend
    drop-down reads this enum via `/api/models`.
    """

    gemma_3_27b = "google/gemma-3-27b-it"
    gpt_oss_120b = "openai/gpt-oss-120b"


# Human-friendly labels for the dropdown.
MODEL_LABELS: dict[ModelChoice, str] = {
    ModelChoice.gemma_3_27b: "Gemma 3 27B (저렴·빠름)",
    ModelChoice.gpt_oss_120b: "GPT-OSS 120B (정밀)",
}


class AnalyzeRequest(BaseModel):
    """Body of `POST /api/analyze`."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    asset: str = Field(min_length=1, max_length=32, description="Ticker or name, e.g. 'NVDA'")
    as_of_date: date = Field(
        default_factory=date.today,
        alias="asOfDate",
        description="Analysis reference date (YYYY-MM-DD)",
    )
    model: ModelChoice = Field(
        default=ModelChoice.gpt_oss_120b,
        description="OpenRouter model id to use for all agents",
    )

    @field_validator("asset")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("asset must not be blank")
        return v


__all__ = ["ModelChoice", "MODEL_LABELS", "AnalyzeRequest"]
