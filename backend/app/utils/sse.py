"""SSE helper utilities — translate `SSEEvent` instances into the shape
`sse-starlette.EventSourceResponse` expects, and provide a manual text
formatter for tests that don't want the full ASGI stack.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.schemas.events import SSEEvent


def format_sse_text(event: SSEEvent) -> str:
    """Format an event as a raw SSE text block (terminated by blank line).

    Suitable for unit tests or for emitting via `StreamingResponse` without
    sse-starlette.
    """
    payload = event.data_json()
    lines = [f"event: {event.event}"]
    for line in payload.splitlines() or [""]:
        lines.append(f"data: {line}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


async def to_sse_stream(events: AsyncIterator[SSEEvent]) -> AsyncIterator[dict[str, str]]:
    """Adapter: turn an async iterator of SSEEvent into sse-starlette dicts."""
    async for evt in events:
        yield evt.to_sse_dict()


__all__ = ["format_sse_text", "to_sse_stream"]
