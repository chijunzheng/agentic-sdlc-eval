"""Event envelope stamping.

Every event in the Event Log carries a common envelope so that downstream
projections can join and group uniformly. The envelope is stamped at append
time; callers provide the event body and the required identity fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = 1

# Required identity fields a caller must supply on every event.
REQUIRED_FIELDS = ("event_type", "repo", "session_id")


def _utc_now_iso() -> str:
    """Current time as a UTC ISO-8601 string with explicit offset."""
    return datetime.now(UTC).isoformat()


def stamp(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return a new envelope-stamped event without mutating the input.

    Validates the required identity fields, fills in ``schema_version`` and a
    UTC ``timestamp`` (unless the caller already supplied one, e.g. on replay),
    and passes every other field — including optional workflow fields
    (``workflow_alias``, ``workflow_fingerprint``, ``issue``) — straight
    through.

    Raises:
        TypeError: if ``event`` is not a mapping.
        ValueError: if a required identity field is missing or empty.
    """
    if not isinstance(event, Mapping):
        raise TypeError(f"event must be a mapping, got {type(event).__name__}")

    missing = [
        field
        for field in REQUIRED_FIELDS
        if event.get(field) in (None, "")
    ]
    if missing:
        raise ValueError(f"event missing required field(s): {', '.join(missing)}")

    stamped: dict[str, Any] = dict(event)
    stamped["schema_version"] = SCHEMA_VERSION
    stamped.setdefault("timestamp", _utc_now_iso())
    return stamped
