"""Manual smoke test for Phase 1 data fetcher.

Usage:
    python -m scripts.smoke NVDA 2026-05-13

Runs the data fetcher end-to-end against live yfinance (and FRED/News if keys
are configured) and prints a concise summary. Useful for verifying the
backend environment without standing up the HTTP server.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date


def _parse_args() -> tuple[str, date]:
    if len(sys.argv) < 2:
        print("usage: python -m scripts.smoke <ASSET> [YYYY-MM-DD]")
        sys.exit(2)
    asset = sys.argv[1]
    if len(sys.argv) >= 3:
        as_of = date.fromisoformat(sys.argv[2])
    else:
        as_of = date.today()
    return asset, as_of


async def _main() -> None:
    asset, as_of = _parse_args()
    # Imports inside main so `--help` style errors are fast
    from app.data.fetcher import fetch_all

    def on_progress(source: str, status: str) -> None:
        print(f"  [{status:5}] {source}")

    print(f"Fetching {asset} as of {as_of} ...")
    result = await fetch_all(asset, as_of, on_progress=on_progress)

    summary = result.summary()
    print("\nSummary:")
    print(json.dumps(summary, indent=2, default=str))

    if result.prices and result.prices.indicators:
        ind = result.prices.indicators
        print("\nLatest indicators:")
        print(json.dumps(ind.model_dump(), indent=2))

    if result.fundamentals:
        print(
            f"\nQuarters returned: {len(result.fundamentals.quarters)}, "
            f"PE(t): {result.fundamentals.ratios.pe_trailing}"
        )

    if result.errors:
        print("\nErrors:")
        for err in result.errors:
            print(f"  - {err}")


if __name__ == "__main__":
    asyncio.run(_main())
