"""``collect(repo)``: incremental, reviewer-agnostic GitHub snapshots.

One pass fetches five entity types for a repo through the ``gh`` CLI and writes
them to per-entity JSONL snapshots under the data dir:

* ``issues`` — pure issues (the PRs GitHub folds into the issues endpoint are
  dropped; they are captured as ``pulls``)
* ``pulls`` — pull requests
* ``reviews`` — PR reviews, captured identically for bot and human authors
* ``review_comments`` — inline PR review comments
* ``ci_runs`` — GitHub Actions workflow runs

**Incremental.** A per-repo watermark holds the highest ``updated_at`` seen on
the last successful run. The next run passes it as ``since`` to the issues
endpoint (server-side filtering) and filters pulls and CI runs client-side, so
only changed items are fetched. Reviews and review comments are fetched only for
the pulls that actually changed.

**Resumes safely.** The watermark is written *last*, only after every fetch and
snapshot write succeeds. A failure mid-run leaves the previous watermark and the
previous snapshots intact (snapshot writes are atomic), so a retry re-covers the
same window without gaps.

**Reviewer-agnostic (Layer-0 Rule).** Records are stored exactly as GitHub
returns them. A review's ``user.type`` (``Bot`` vs ``User``) and ``user.login``
are ordinary fields; the snapshot shape is identical whether the reviewer is
Codex, CodeRabbit, Copilot, or a human, and no author-type filtering is applied.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sdlc_eval.github.gh import GhRunner, run_gh_api
from sdlc_eval.github.store import (
    read_watermark,
    upsert_snapshot,
    write_watermark,
)

ENTITY_TYPES = ("issues", "pulls", "reviews", "review_comments", "ci_runs")

# GitHub caps list pages at 100 items; request the max to minimise round trips.
_PER_PAGE = "100"


@dataclass(frozen=True)
class CollectResult:
    """Outcome of a ``collect`` run.

    ``counts`` maps each entity type to the number of records fetched this run
    (changed items only on an incremental run). ``watermark`` is the high-water
    ``updated_at`` recorded, or None if the run found nothing.
    """

    repo: str
    counts: dict[str, int] = field(default_factory=dict)
    watermark: str | None = None


def _updated_at(record: Mapping[str, Any]) -> str | None:
    value = record.get("updated_at")
    return value if isinstance(value, str) else None


def _is_pull_request(issue: Mapping[str, Any]) -> bool:
    """GitHub's issues endpoint also returns PRs; they carry ``pull_request``."""
    return "pull_request" in issue


def _changed_since(
    records: Iterable[Mapping[str, Any]], since: str | None
) -> list[dict[str, Any]]:
    """Client-side filter to records updated strictly after ``since``."""
    items = [dict(record) for record in records]
    if since is None:
        return items
    return [r for r in items if (_updated_at(r) or "") > since]


def _max_updated_at(records: Iterable[Mapping[str, Any]], current: str | None) -> str | None:
    """Return the latest ``updated_at`` across ``records`` and ``current``."""
    high = current
    for record in records:
        updated = _updated_at(record) or record.get("submitted_at")
        if isinstance(updated, str) and (high is None or updated > high):
            high = updated
    return high


def _fetch_issues(runner: GhRunner, repo: str, since: str | None) -> list[dict[str, Any]]:
    params = {"state": "all", "sort": "updated", "direction": "desc", "per_page": _PER_PAGE}
    if since is not None:
        params["since"] = since
    raw = runner(f"repos/{repo}/issues", params=params, slurp=True) or []
    # Drop PRs so issues.jsonl stays pure issues; PRs are captured via /pulls.
    return [dict(item) for item in raw if not _is_pull_request(item)]


def _fetch_pulls(runner: GhRunner, repo: str, since: str | None) -> list[dict[str, Any]]:
    params = {"state": "all", "sort": "updated", "direction": "desc", "per_page": _PER_PAGE}
    raw = runner(f"repos/{repo}/pulls", params=params, slurp=True) or []
    # The pulls endpoint has no ``since``; filter to changed items client-side.
    return _changed_since(raw, since)


def _fetch_pull_reviews(
    runner: GhRunner, repo: str, number: Any
) -> list[dict[str, Any]]:
    raw = runner(f"repos/{repo}/pulls/{number}/reviews", slurp=True) or []
    return [dict(item) for item in raw]


def _fetch_pull_review_comments(
    runner: GhRunner, repo: str, number: Any
) -> list[dict[str, Any]]:
    raw = runner(f"repos/{repo}/pulls/{number}/comments", slurp=True) or []
    return [dict(item) for item in raw]


def _fetch_ci_runs(runner: GhRunner, repo: str, since: str | None) -> list[dict[str, Any]]:
    params = {"per_page": _PER_PAGE}
    response = runner(f"repos/{repo}/actions/runs", params=params, slurp=False) or {}
    runs = response.get("workflow_runs", []) if isinstance(response, Mapping) else []
    return _changed_since(runs, since)


def collect(repo: str, *, runner: GhRunner = run_gh_api) -> CollectResult:
    """Snapshot ``repo``'s issues, PRs, reviews, comments, and CI runs.

    Args:
        repo: The repo identifier, ``owner/name``.
        runner: The gh-api seam. Defaults to the real ``gh`` subprocess wrapper;
            tests inject a recorded runner so no network call is made.

    Returns:
        A :class:`CollectResult` with per-entity fetch counts and the new
        watermark.

    Raises:
        Any error raised by ``runner`` (e.g. ``GhError``) propagates so the run
        fails loudly. The watermark and existing snapshots are left untouched on
        failure, so a retry resumes safely.
    """
    since = read_watermark(repo)

    issues = _fetch_issues(runner, repo, since)
    pulls = _fetch_pulls(runner, repo, since)

    reviews: list[dict[str, Any]] = []
    review_comments: list[dict[str, Any]] = []
    for pull in pulls:
        number = pull.get("number")
        if number is None:
            continue
        reviews.extend(_fetch_pull_reviews(runner, repo, number))
        review_comments.extend(_fetch_pull_review_comments(runner, repo, number))

    ci_runs = _fetch_ci_runs(runner, repo, since)

    fetched = {
        "issues": issues,
        "pulls": pulls,
        "reviews": reviews,
        "review_comments": review_comments,
        "ci_runs": ci_runs,
    }

    # All fetches succeeded; persist snapshots, then advance the watermark last.
    counts: dict[str, int] = {}
    for entity, records in fetched.items():
        counts[entity] = upsert_snapshot(repo, entity, records)

    new_watermark = since
    for records in (issues, pulls, reviews, review_comments, ci_runs):
        new_watermark = _max_updated_at(records, new_watermark)

    if new_watermark is not None and new_watermark != since:
        write_watermark(repo, new_watermark)

    return CollectResult(repo=repo, counts=counts, watermark=new_watermark)
