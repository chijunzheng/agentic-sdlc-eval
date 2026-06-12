"""Thin seam over the ``gh api`` CLI.

The collector talks to GitHub exclusively through ``gh`` so it inherits the
user's existing auth, host config, and rate-limit handling rather than managing
tokens itself. This module is the single point where a subprocess is spawned,
which keeps the rest of the collector pure and lets tests inject a recorded
``GhRunner`` instead of touching the network.

Pagination is handled by ``gh`` itself: ``--paginate`` walks every page of a
``Link``-header-paginated endpoint, and ``--slurp`` collects the pages into a
JSON array of arrays which we flatten. ``gh`` also backs off on secondary rate
limits, so callers get rate-limit-aware fetching for free.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from typing import Any, Protocol


class GhError(RuntimeError):
    """A ``gh api`` invocation failed or returned unparseable output."""


class GhRunner(Protocol):
    """Fetch a GitHub REST endpoint and return parsed JSON.

    Implementations must be reviewer-agnostic and side-effect free beyond the
    network call: the same ``path``/``params`` always yields the same shape.
    """

    def __call__(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = ...,
        slurp: bool = ...,
    ) -> Any: ...


def _build_command(
    path: str, params: Mapping[str, str] | None, slurp: bool
) -> list[str]:
    """Build the ``gh api`` argument vector for a paginated GET."""
    # --method GET is mandatory, not decorative: adding -f fields switches
    # gh api to POST unless the method is pinned, and this seam is read-only
    # by contract (POST repos/*/issues would create an issue).
    cmd = ["gh", "api", path, "--method", "GET", "--paginate"]
    if slurp:
        # --slurp wraps each page in an array; we flatten below.
        cmd.append("--slurp")
    for key, value in (params or {}).items():
        # With the method pinned to GET, -f fields map to query parameters.
        cmd.extend(["-f", f"{key}={value}"])
    return cmd


def _flatten_slurped(pages: Any) -> list[Any]:
    """Flatten ``gh --slurp`` output (a list of pages) into one list."""
    if not isinstance(pages, list):
        raise GhError(f"expected a list of pages from --slurp, got {type(pages).__name__}")
    flattened: list[Any] = []
    for page in pages:
        if isinstance(page, list):
            flattened.extend(page)
        else:
            flattened.append(page)
    return flattened


def run_gh_api(
    path: str,
    *,
    params: Mapping[str, str] | None = None,
    slurp: bool = False,
) -> Any:
    """Run ``gh api <path>`` and return the parsed JSON response.

    Args:
        path: The REST path, e.g. ``repos/owner/name/issues``.
        params: Query parameters, sent as ``-f key=value`` fields.
        slurp: When True, request ``--slurp`` and flatten the paginated pages
            into a single list. Use for endpoints that return a JSON array.

    Returns:
        Parsed JSON: a list (slurped/array endpoints) or a dict (object
        endpoints).

    Raises:
        GhError: if ``gh`` exits non-zero or emits output that is not JSON.
    """
    cmd = _build_command(path, params, slurp)
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:  # gh not installed / not on PATH
        raise GhError(f"failed to invoke gh: {error}") from error

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise GhError(f"gh api {path} failed (exit {completed.returncode}): {detail}")

    output = completed.stdout.strip()
    if not output:
        # An empty body from a paginated list endpoint means zero items.
        return [] if slurp else {}

    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as error:
        raise GhError(f"gh api {path} returned invalid JSON: {error}") from error

    if slurp:
        return _flatten_slurped(parsed)
    return parsed
