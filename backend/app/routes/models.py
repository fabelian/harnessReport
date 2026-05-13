"""GET /api/models — list selectable OpenRouter models for the frontend dropdown."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.schemas.inputs import MODEL_LABELS, ModelChoice

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models")
async def list_models() -> dict:
    settings = get_settings()
    items = [
        {
            "id": choice.value,
            "label": MODEL_LABELS[choice],
            "default": choice.value == settings.openrouter_default_model,
        }
        for choice in ModelChoice
    ]
    return {
        "models": items,
        "default": settings.openrouter_default_model,
        "openrouter_configured": settings.openrouter_configured,
    }
