"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import analyze, health, jobs, models
from app.storage.db import init_db

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("equity-research")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info(
        "startup ok | model=%s | openrouter_configured=%s | cors=%s",
        settings.openrouter_default_model,
        settings.openrouter_configured,
        settings.cors_origin_list,
    )
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Equity Research Backend",
    version="0.3.0",
    description="OpenRouter-based multi-agent equity research API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(models.router)
app.include_router(analyze.router)
app.include_router(jobs.router)


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "service": "equity-research-backend",
        "version": app.version,
        "docs": "/docs",
        "health": "/api/health",
        "analyze": "/api/analyze",
        "jobs": "/api/jobs",
    }
