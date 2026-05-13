"""SSE event payload schemas emitted by the orchestrator."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

EventType = Literal[
    "job_start",
    "data_fetch_start",
    "data_fetch_progress",
    "data_fetch_done",
    "agent_start",
    "agent_done",
    "reviewer_start",
    "reviewer_done",
    "error",
    "done",
]


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


@dataclass(slots=True)
class SSEEvent:
    """A single Server-Sent Event payload.

    `to_sse_dict()` returns the shape `sse-starlette` consumes:
        {"event": <type>, "data": <serialized JSON string>}
    """

    event: EventType
    data: dict[str, Any]

    def data_json(self) -> str:
        return json.dumps(self.data, default=_json_default, ensure_ascii=False)

    def to_sse_dict(self) -> dict[str, str]:
        return {"event": self.event, "data": self.data_json()}


__all__ = ["EventType", "SSEEvent"]
