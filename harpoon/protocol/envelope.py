"""Wire envelope: every WS message is `{type, seq, payload}`.

The dispatcher validates the envelope shape before handing the payload to the
primitive handler. `seq` is a per-session monotonically increasing counter the
client maintains; the server uses it for replay detection and audit logs.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class Envelope(BaseModel):
    """Outer wrapper for every WebSocket message in either direction."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., min_length=1, max_length=128)
    seq: int = Field(default=0, ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)


def wrap(type_: str, payload: dict[str, Any] | None = None, seq: int = 0) -> dict[str, Any]:
    """Build an outgoing envelope dict ready for json.dumps."""
    return {"type": type_, "seq": seq, "payload": payload or {}}
