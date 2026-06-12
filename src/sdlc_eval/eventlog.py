"""The eventlog deep module: the append-only spine of the system.

Public surface is intentionally one function, ``append(event)``. It stamps the
common envelope and appends exactly one JSON line to the repo's Event Log using
``O_APPEND`` semantics. POSIX guarantees that an ``O_APPEND`` write smaller than
``PIPE_BUF`` is atomic, so concurrent hook writers from parallel processes never
produce interleaved or torn lines (ADR 0003).

Keep this interface minimal and stable: three Wave-1 modules build directly on
``append()``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from sdlc_eval.envelope import SCHEMA_VERSION, stamp
from sdlc_eval.paths import repo_events_dir

__all__ = ["append", "SCHEMA_VERSION"]

LOG_FILENAME = "events.jsonl"


def _serialize(event: Mapping[str, Any]) -> bytes:
    """Render an event as a single newline-terminated JSON line (bytes).

    ``json.dumps`` escapes any embedded newlines, so one event is always one
    physical line — a precondition for line-oriented atomic appends.
    """
    line = json.dumps(event, ensure_ascii=False, sort_keys=False, separators=(",", ":"))
    return (line + "\n").encode("utf-8")


def append(event: Mapping[str, Any]) -> dict[str, Any]:
    """Stamp ``event`` with the envelope and append it to the Event Log.

    Args:
        event: The event body. Must include the required identity fields
            ``event_type``, ``repo`` and ``session_id``. Optional workflow
            fields (``workflow_alias``, ``workflow_fingerprint``, ``issue``)
            and any other keys pass through untouched.

    Returns:
        The full envelope-stamped event that was written.

    Raises:
        TypeError: if ``event`` is not a mapping.
        ValueError: if a required identity field is missing.
        OSError: if the log cannot be written.
    """
    stamped = stamp(event)
    repo_dir = repo_events_dir(str(stamped["repo"]))

    try:
        repo_dir.mkdir(parents=True, exist_ok=True)
        log_path = repo_dir / LOG_FILENAME
        payload = _serialize(stamped)
        # O_APPEND makes the kernel position the write at end-of-file
        # atomically; a single write() of a sub-PIPE_BUF payload is atomic
        # across concurrent writers, so lines never interleave.
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
    except OSError as error:
        raise OSError(
            f"failed to append event to Event Log at {repo_dir}: {error}"
        ) from error

    return stamped
