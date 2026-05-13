"""SSE event formatting helpers."""
from __future__ import annotations

from datetime import date

from app.schemas.events import SSEEvent
from app.utils.sse import format_sse_text


def test_event_serializes_dates() -> None:
    evt = SSEEvent("job_start", {"jobId": "abc", "asOfDate": date(2026, 5, 13)})
    payload = evt.data_json()
    assert '"asOfDate": "2026-05-13"' in payload


def test_format_sse_text_shape() -> None:
    evt = SSEEvent("agent_done", {"agent": "fundamental"})
    text = format_sse_text(evt)
    assert text.startswith("event: agent_done\n")
    assert "data: " in text
    assert text.endswith("\n\n")
