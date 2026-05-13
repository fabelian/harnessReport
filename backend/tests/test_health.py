"""Smoke test for the health endpoint."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "openrouter_configured" in body
        assert "default_model" in body


def test_root_redirect_info() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "equity-research-backend"
