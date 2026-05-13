"""Health check endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "openrouter_configured": settings.openrouter_configured,
        "default_model": settings.openrouter_default_model,
    }
