"""SessionStart hook adapter: emit a ``session_started`` event.

Claude Code invokes the SessionStart hook with a JSON payload on stdin that
includes at least ``session_id`` and ``cwd``. This adapter maps that payload to
an Event Log append. It is Auto-Capture (Layer 0): no skill cooperation
required, so it tags events with ``source="hook"``.

Attribution (repo + issue) is delegated to :mod:`sdlc_eval.context_resolver`,
which infers the Issue Attempt from the git remote and branch/commit
conventions. Unresolvable contexts are flagged ``attributed=False`` and still
recorded — events are never dropped (PRD story 22).

Hooks must never break the host session, so :func:`handle_session_start`
returns ``None`` instead of raising on any malformed input or write failure.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from sdlc_eval import eventlog
from sdlc_eval.context_resolver import ResolvedContext, resolve

EVENT_TYPE = "session_started"
SOURCE = "hook"


def _fallback_repo(payload: Mapping[str, Any]) -> str | None:
    """Last-resort repo label when the resolver cannot determine one.

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


def _attribution(payload: Mapping[str, Any]) -> ResolvedContext:
    """Resolve attribution, retaining a basename repo when the resolver finds none.

    The resolver returns ``repo=None`` outside a git worktree; for the Event
    Log to still group by repo we fall back to the cwd basename, but keep the
    event flagged unattributed so the attribution rate stays honest.
    """
    ctx = resolve(payload.get("cwd"), payload)
    if ctx.repo:
        return ctx
    return ResolvedContext(
        repo=_fallback_repo(payload),
        issue=ctx.issue,
        attributed=ctx.attributed,
    )


def handle_session_start(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """Append a ``session_started`` event derived from a hook payload.

    Returns the stamped event on success, or ``None`` if the payload is
    unusable or the append fails. Never raises.
    """
    try:
        session_id = payload.get("session_id")
        if not session_id:
            return None

        ctx = _attribution(payload)
        if not ctx.repo:
            return None

        event: dict[str, Any] = {
            "event_type": EVENT_TYPE,
            "repo": ctx.repo,
            "session_id": str(session_id),
            "source": SOURCE,
            "attributed": ctx.attributed,
        }
        if ctx.issue is not None:
            event["issue"] = ctx.issue

        return eventlog.append(event)
    except Exception as error:  # noqa: BLE001 - hooks must never break the session
        print(f"sdlc-eval session_start hook failed: {error}", file=sys.stderr)
        return None
