"""The context_resolver deep module: attribute every event to an Issue Attempt.

Auto-Capture (Layer 0) sees events with no semantic context — just a working
directory and whatever the hook payload carries. This module infers the two
identity fields every event needs to join onto an Issue Attempt:

* **repo** — from the git ``origin`` remote (normalized to ``owner/name``),
  falling back to the worktree basename when there is no remote.
* **issue** — from branch naming conventions (``issue-14-*``, ``14-*``,
  ``feature/14-*``) and from commit/PR references in the payload
  (``fixes #14``, ``closes #14``, a bare ``#14``).

When neither a repo nor an issue can be determined, the result is flagged
*unattributed* and returned anyway — events are never dropped (PRD story 22).
Resolution never raises: a hook must never break the host session, so every
failure path collapses to an explicit unattributed marker.

The two inference helpers (:func:`issue_from_branch`, :func:`issue_from_text`)
are pure and exhaustively fixture-tested; the git-backed parts are thin shells
over ``git`` invocations.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

__all__ = [
    "ResolvedContext",
    "resolve",
    "issue_from_branch",
    "issue_from_text",
]

# A branch encodes its issue as a leading number, optionally behind a single
# ``type/`` prefix (feature/, fix/, issue/, bugfix/, …) or an ``issue-`` word.
# The number must be delimited by a non-digit (``-``, ``/`` or end-of-string),
# so ``v2-foo`` is not read as issue 2 but ``2024-archive`` is issue 2024.
_BRANCH_ISSUE_RE = re.compile(
    r"""
    ^
    (?:[A-Za-z]+/)?        # optional single type prefix, e.g. feature/
    (?:issue-)?            # optional issue- word prefix
    (?P<issue>\d+)         # the issue number
    (?:[-/]|$)             # delimited by - or / or end of branch name
    """,
    re.VERBOSE,
)

# Commit-message / PR references: an optional closing keyword then ``#<n>``.
# A bare ``#14`` also counts. Case-insensitive; first match in the text wins.
_TEXT_ISSUE_RE = re.compile(
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)?\s*#(?P<issue>\d+)",
    re.IGNORECASE,
)

# Payload keys that may carry a commit/PR reference, in priority order.
_TEXT_PAYLOAD_KEYS = ("commit_message", "pr_body", "pr_title", "message")


@dataclass(frozen=True)
class ResolvedContext:
    """The inferred attribution for a single event.

    Immutable by construction (``frozen=True``). ``attributed`` is ``True`` only
    when an issue number was inferred; a known repo with no issue is still
    *unattributed* — the event joins to a repo but not to an Issue Attempt.
    """

    repo: str | None
    issue: int | None
    attributed: bool

    @classmethod
    def unattributed(cls, repo: str | None = None) -> ResolvedContext:
        """An explicit unattributed marker, optionally retaining a known repo."""
        return cls(repo=repo, issue=None, attributed=False)


def issue_from_branch(branch: str) -> int | None:
    """Infer an issue number from a branch name, or ``None``.

    Recognizes ``issue-14-*``, ``14-*`` and ``<prefix>/14-*`` (feature/, fix/,
    bugfix/, issue/, …). A bare leading number counts; a number embedded after
    letters (``v2-foo``) does not.
    """
    if not branch:
        return None
    match = _BRANCH_ISSUE_RE.match(branch)
    if match is None:
        return None
    return int(match.group("issue"))


def issue_from_text(text: str) -> int | None:
    """Infer an issue number from free text (commit message / PR body).

    Returns the first ``#<n>`` reference, with or without a closing keyword
    (``fixes``/``closes``/``resolves``). Returns ``None`` when no reference is
    present.
    """
    if not text:
        return None
    match = _TEXT_ISSUE_RE.search(text)
    if match is None:
        return None
    return int(match.group("issue"))


def _run_git(cwd: str, *args: str) -> str | None:
    """Run ``git -C <cwd> <args>`` and return stripped stdout, or ``None``.

    Any failure — git missing, not a repository, non-zero exit — collapses to
    ``None`` so the caller can fall back to an unattributed result.
    """
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return output or None


def _normalize_remote(url: str) -> str | None:
    """Normalize a git remote URL to ``owner/name``.

    Handles HTTPS (``https://host/owner/name.git``) and SCP-style SSH
    (``git@host:owner/name.git``) forms, stripping a trailing ``.git``.
    """
    cleaned = url.strip()
    if cleaned.endswith(".git"):
        cleaned = cleaned[: -len(".git")]

    # SCP-style SSH: git@host:owner/name
    if "@" in cleaned and ":" in cleaned and "://" not in cleaned:
        cleaned = cleaned.split(":", 1)[1]
    elif "://" in cleaned:
        cleaned = cleaned.split("://", 1)[1]
        # drop the host segment
        cleaned = cleaned.split("/", 1)[1] if "/" in cleaned else cleaned

    cleaned = cleaned.strip("/")
    parts = [p for p in cleaned.split("/") if p]
    if len(parts) < 2:
        return None
    # Take the last two path segments as owner/name.
    return "/".join(parts[-2:])


def _resolve_repo(cwd: str, payload: Mapping[str, Any]) -> str | None:
    """Determine the repo label: payload override → git remote → basename."""
    explicit = payload.get("repo")
    if explicit:
        return str(explicit)

    remote = _run_git(cwd, "config", "--get", "remote.origin.url")
    if remote:
        normalized = _normalize_remote(remote)
        if normalized:
            return normalized

    # No usable remote, but if this is a git worktree fall back to the basename
    # so events still group by repo. Outside a repo, return None.
    if _run_git(cwd, "rev-parse", "--is-inside-work-tree") == "true":
        name = PurePosixPath(cwd).name
        return name or None
    return None


def _resolve_issue(cwd: str, payload: Mapping[str, Any]) -> int | None:
    """Determine the issue number: explicit → branch convention → payload refs.

    A branch convention is a stronger signal than a commit/PR reference (the
    branch is what the developer is actually on), so it wins over payload text.
    """
    explicit = payload.get("issue")
    if isinstance(explicit, int):
        return explicit
    if isinstance(explicit, str) and explicit.isdigit():
        return int(explicit)

    branch = _run_git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    # Detached HEAD reports "HEAD"; that carries no issue convention.
    if branch and branch != "HEAD":
        from_branch = issue_from_branch(branch)
        if from_branch is not None:
            return from_branch

    for key in _TEXT_PAYLOAD_KEYS:
        value = payload.get(key)
        if isinstance(value, str):
            from_text = issue_from_text(value)
            if from_text is not None:
                return from_text

    return None


def resolve(cwd: str | None, payload: Mapping[str, Any] | None) -> ResolvedContext:
    """Infer the Issue Attempt attribution for an event.

    Args:
        cwd: The working directory the event originated from.
        payload: The hook payload; may carry ``repo``/``issue`` overrides or
            commit/PR text. ``None`` and non-mapping values are tolerated.

    Returns:
        A :class:`ResolvedContext`. ``attributed`` is ``True`` only when an
        issue number was inferred. Unresolvable contexts are flagged, never
        dropped. This function never raises.
    """
    safe_payload: Mapping[str, Any] = payload if isinstance(payload, Mapping) else {}

    if not cwd:
        repo = str(safe_payload.get("repo")) if safe_payload.get("repo") else None
        issue = _issue_from_payload_only(safe_payload)
        if issue is not None:
            return ResolvedContext(repo=repo, issue=issue, attributed=True)
        return ResolvedContext.unattributed(repo=repo)

    try:
        if not Path(cwd).exists() and not safe_payload.get("repo"):
            return _resolve_from_payload_only(safe_payload)

        repo = _resolve_repo(cwd, safe_payload)
        issue = _resolve_issue(cwd, safe_payload)
    except Exception:  # noqa: BLE001 - resolution must never break the host
        return _resolve_from_payload_only(safe_payload)

    if issue is None:
        return ResolvedContext.unattributed(repo=repo)
    return ResolvedContext(repo=repo, issue=issue, attributed=True)


def _issue_from_payload_only(payload: Mapping[str, Any]) -> int | None:
    """Infer an issue from payload fields alone (no git access)."""
    explicit = payload.get("issue")
    if isinstance(explicit, int):
        return explicit
    if isinstance(explicit, str) and explicit.isdigit():
        return int(explicit)
    for key in _TEXT_PAYLOAD_KEYS:
        value = payload.get(key)
        if isinstance(value, str):
            from_text = issue_from_text(value)
            if from_text is not None:
                return from_text
    return None


def _resolve_from_payload_only(payload: Mapping[str, Any]) -> ResolvedContext:
    """Build a context from payload fields when git is unavailable."""
    repo = str(payload.get("repo")) if payload.get("repo") else None
    issue = _issue_from_payload_only(payload)
    if issue is not None:
        return ResolvedContext(repo=repo, issue=issue, attributed=True)
    return ResolvedContext.unattributed(repo=repo)
