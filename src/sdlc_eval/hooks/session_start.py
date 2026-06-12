"""SessionStart hook adapter: emit a ``session_started`` event.

Claude Code invokes the SessionStart hook with a JSON payload on stdin that
includes at least ``session_id`` and ``cwd``. This adapter maps that payload to
an Event Log append. It is Auto-Capture (Layer 0): no skill cooperation
required, so it tags events with ``source="hook"``.

Hooks must never break the host session, so :func:`handle_session_start`
returns ``None`` instead of raising on any malformed input or write failure.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from sdlc_eval import eventlog

EVENT_TYPE = "session_started"
SOURCE = "hook"


def _resolve_repo(payload: Mapping[str, Any]) -> str | None:
    """Determine the repo label from the payload.

    An explicit ``repo`` wins; otherwise derive it from the basename of
    ``cwd``. Returns ``None`` if neither is available.
    """
    repo = payload.get("repo")
    if repo:
        return str(repo)

    cwd = payload.get("cwd")
    if not cwd:
        return None

    name = PurePosixPath(str(cwd)).name
    return name or None


def handle_session_start(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """Append a ``session_started`` event derived from a hook payload.

    Returns the stamped event on success, or ``None`` if the payload is
    unusable or the append fails. Never raises.
    """
    try:
        session_id = payload.get("session_id")
        if not session_id:
            return None

        repo = _resolve_repo(payload)
        if not repo:
            return None

        return eventlog.append(
            {
                "event_type": EVENT_TYPE,
                "repo": repo,
                "session_id": str(session_id),
                "source": SOURCE,
            }
        )
    except Exception as error:  # noqa: BLE001 - hooks must never break the session
        print(f"sdlc-eval session_start hook failed: {error}", file=sys.stderr)
        return None
