"""Probe the OpenRouter catalog for model IDs.

Usage:
    python -m scripts.list_models                # full list
    python -m scripts.list_models gemma          # filter by substring
    python -m scripts.list_models "gpt-oss"

Reads `OPENROUTER_API_KEY` from `.env`. Outputs id, context length, and
pricing so you can pick the correct model for `OPENROUTER_DEFAULT_MODEL`
and the `ModelChoice` enum in `app/schemas/inputs.py`.
"""
from __future__ import annotations

import asyncio
import sys

import httpx

from app.config import get_settings


async def _main() -> None:
    needle = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    settings = get_settings()
    if not settings.openrouter_api_key:
        print("OPENROUTER_API_KEY missing — set it in backend/.env first.")
        sys.exit(1)

    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.get(
            f"{settings.openrouter_base_url}/models",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        )
        resp.raise_for_status()
        catalog = resp.json().get("data", [])

    rows: list[tuple[str, str, str, str]] = []
    for entry in catalog:
        mid = entry.get("id", "")
        if needle and needle not in mid.lower():
            continue
        name = entry.get("name", "")
        ctx = str(entry.get("context_length") or "")
        pricing = entry.get("pricing") or {}
        prompt_p = pricing.get("prompt") or ""
        compl_p = pricing.get("completion") or ""
        rows.append((mid, name, ctx, f"in {prompt_p} / out {compl_p}"))

    rows.sort(key=lambda r: r[0])
    if not rows:
        print(f"no models matched '{needle}'")
        return

    width_id = max(len(r[0]) for r in rows)
    width_name = min(60, max(len(r[1]) for r in rows))
    for mid, name, ctx, price in rows:
        print(f"{mid:<{width_id}}  {name[:width_name]:<{width_name}}  ctx={ctx}  {price}")


if __name__ == "__main__":
    asyncio.run(_main())
