"""Fixture-driven tests for the github_collector ``collect`` orchestration.

A recorded ``RecordingRunner`` replays JSON captured from real ``gh api``
responses so these tests never touch the network. The router keys off the REST
path and the presence of a ``since`` parameter so a single runner can serve both
the initial sync and the incremental second run.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from sdlc_eval.github import collect
from sdlc_eval.github.store import read_snapshot, read_watermark, write_watermark

FIXTURES = Path(__file__).parent / "fixtures" / "github"

REPO = "o/r"


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class RecordingRunner:
    """Replay recorded gh-api responses keyed by path + ``since`` presence.

    ``incremental`` flips which body each list endpoint returns, modelling
    GitHub's ``since``/``sort=updated`` filtering server-side for the issues
    endpoint and giving the collector a smaller working set for everything else.
    """

    def __init__(self, *, incremental: bool = False) -> None:
        self.incremental = incremental
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        slurp: bool = False,
    ) -> Any:
        params = dict(params or {})
        self.calls.append((path, params))

        pr_match = re.search(r"/pulls/(\d+)/(reviews|comments)$", path)
        if pr_match:
            number, kind = pr_match.group(1), pr_match.group(2)
            return self._pr_subresource(number, kind)

        if path.endswith("/issues"):
            name = "incremental_issues" if self.incremental else "initial_issues"
            return _load(f"{name}.json")
        if path.endswith("/pulls"):
            name = "incremental_pulls" if self.incremental else "initial_pulls"
            return _load(f"{name}.json")
        if path.endswith("/actions/runs"):
            name = "incremental_ci_runs" if self.incremental else "initial_ci_runs"
            return _load(f"{name}.json")

        raise AssertionError(f"unexpected path requested: {path}")

    def _pr_subresource(self, number: str, kind: str) -> Any:
        if kind == "reviews":
            if self.incremental and number == "7":
                return _load("incremental_reviews_pr7.json")
            return _load(f"reviews_pr{number}.json")
        # review comments
        return _load(f"review_comments_pr{number}.json")


# --------------------------------------------------------------------------- #
# Acceptance criterion 1: collect snapshots all five entity types.
# --------------------------------------------------------------------------- #


def test_collect_snapshots_issues(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    issues = read_snapshot(REPO, "issues")
    numbers = {i["number"] for i in issues}
    # The two real issues are present; the PR (#7) returned by the issues
    # endpoint is excluded so issues.jsonl stays pure issues.
    assert numbers == {1, 2}


def test_collect_snapshots_pulls(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    pulls = read_snapshot(REPO, "pulls")
    assert {p["number"] for p in pulls} == {3, 7}


def test_collect_snapshots_reviews(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    reviews = read_snapshot(REPO, "reviews")
    assert {r["id"] for r in reviews} == {5001, 5002, 5003}


def test_collect_snapshots_review_comments(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    comments = read_snapshot(REPO, "review_comments")
    assert {c["id"] for c in comments} == {6001, 6002}


def test_collect_snapshots_ci_runs(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    runs = read_snapshot(REPO, "ci_runs")
    assert {r["id"] for r in runs} == {9001, 9002}


def test_collect_returns_per_entity_counts(data_dir: Path) -> None:
    result = collect(REPO, runner=RecordingRunner())
    assert result.counts["issues"] == 2
    assert result.counts["pulls"] == 2
    assert result.counts["reviews"] == 3
    assert result.counts["review_comments"] == 2
    assert result.counts["ci_runs"] == 2


# --------------------------------------------------------------------------- #
# Acceptance criterion 3: reviewer-agnostic snapshot shape (Layer-0 Rule).
# --------------------------------------------------------------------------- #


def test_review_snapshot_shape_is_reviewer_agnostic(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    reviews = {r["id"]: r for r in read_snapshot(REPO, "reviews")}

    bot_review = reviews[5001]  # Codex bot
    human_review = reviews[5002]  # human carol

    assert bot_review["user"]["type"] == "Bot"
    assert human_review["user"]["type"] == "User"
    # Identical key set regardless of author type — the Layer-0 invariant.
    assert set(bot_review) == set(human_review)


def test_review_comment_shape_is_reviewer_agnostic(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    comments = {c["id"]: c for c in read_snapshot(REPO, "review_comments")}
    assert set(comments[6001]) == set(comments[6002])


def test_bot_and_human_reviews_both_present(data_dir: Path) -> None:
    """No author-type filtering: bot AND human reviews are both captured."""
    collect(REPO, runner=RecordingRunner())
    authors = {r["user"]["type"] for r in read_snapshot(REPO, "reviews")}
    assert authors == {"Bot", "User"}


# --------------------------------------------------------------------------- #
# Acceptance criterion 2: incremental second run uses the watermark.
# --------------------------------------------------------------------------- #


def test_first_run_sends_no_since(data_dir: Path) -> None:
    runner = RecordingRunner()
    collect(REPO, runner=runner)
    issues_call = next(c for c in runner.calls if c[0].endswith("/issues"))
    assert "since" not in issues_call[1]


def test_first_run_records_watermark(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    # Highest updated_at across all fetched items is PR #7 at 2026-06-06T15:00:00Z.
    assert read_watermark(REPO) == "2026-06-06T15:00:00Z"


def test_second_run_sends_since_from_watermark(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    runner = RecordingRunner(incremental=True)
    collect(REPO, runner=runner)
    issues_call = next(c for c in runner.calls if c[0].endswith("/issues"))
    assert issues_call[1].get("since") == "2026-06-06T15:00:00Z"


def test_second_run_advances_watermark(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    collect(REPO, runner=RecordingRunner(incremental=True))
    # Highest updated_at now is the re-edited issue #1 at 2026-06-08T10:00:00Z.
    assert read_watermark(REPO) == "2026-06-08T10:00:00Z"


def test_incremental_run_merges_not_replaces(data_dir: Path) -> None:
    """A second run keeps prior records and updates changed ones."""
    collect(REPO, runner=RecordingRunner())
    collect(REPO, runner=RecordingRunner(incremental=True))

    issues = {i["number"]: i for i in read_snapshot(REPO, "issues")}
    # Issue #2 was untouched on the second run but must survive.
    assert set(issues) == {1, 2}
    # Issue #1 reflects the incremental edit.
    assert issues[1]["state"] == "closed"
    assert issues[1]["title"] == "First issue (edited)"


def test_incremental_run_only_fetches_changed_pull_subresources(data_dir: Path) -> None:
    """Only PRs updated since the watermark have reviews/comments re-fetched."""
    collect(REPO, runner=RecordingRunner())
    runner = RecordingRunner(incremental=True)
    collect(REPO, runner=runner)

    review_paths = [c[0] for c in runner.calls if c[0].endswith("/reviews")]
    # PR #3 was not updated since the watermark, so it is not re-walked.
    assert any("/pulls/7/reviews" in p for p in review_paths)
    assert not any("/pulls/3/reviews" in p for p in review_paths)


def test_incremental_run_adds_new_review(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    collect(REPO, runner=RecordingRunner(incremental=True))
    review_ids = {r["id"] for r in read_snapshot(REPO, "reviews")}
    # The new approval (5004) is added; the prior bot review (5003 on PR#3) stays.
    assert 5004 in review_ids
    assert 5003 in review_ids


def test_incremental_run_adds_new_ci_run(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    collect(REPO, runner=RecordingRunner(incremental=True))
    run_ids = {r["id"] for r in read_snapshot(REPO, "ci_runs")}
    assert 9003 in run_ids
    assert {9001, 9002}.issubset(run_ids)


# --------------------------------------------------------------------------- #
# Acceptance criterion 4: failures resume safely (watermark only advances on
# a fully successful run).
# --------------------------------------------------------------------------- #


def test_watermark_not_advanced_when_run_fails(data_dir: Path) -> None:
    write_watermark(REPO, "2026-06-01T00:00:00Z")

    class FailingRunner(RecordingRunner):
        def __call__(self, path: str, **kwargs: Any) -> Any:
            if path.endswith("/actions/runs"):
                raise RuntimeError("rate limited")
            return super().__call__(path, **kwargs)

    with pytest.raises(RuntimeError):
        collect(REPO, runner=FailingRunner())

    # The prior watermark survives so a retry re-fetches the same window.
    assert read_watermark(REPO) == "2026-06-01T00:00:00Z"


def test_partial_failure_does_not_corrupt_existing_snapshot(data_dir: Path) -> None:
    collect(REPO, runner=RecordingRunner())
    before = read_snapshot(REPO, "issues")

    class FailingRunner(RecordingRunner):
        def __init__(self) -> None:
            super().__init__(incremental=True)

        def __call__(self, path: str, **kwargs: Any) -> Any:
            if path.endswith("/actions/runs"):
                raise RuntimeError("network down")
            return super().__call__(path, **kwargs)

    with pytest.raises(RuntimeError):
        collect(REPO, runner=FailingRunner())

    after = read_snapshot(REPO, "issues")
    # Issues already on disk are never lost even though the run aborted.
    assert {i["number"] for i in after} == {i["number"] for i in before}


# --------------------------------------------------------------------------- #
# Empty-repo edge case.
# --------------------------------------------------------------------------- #


def test_collect_skips_pull_without_number(data_dir: Path) -> None:
    """A malformed pull lacking a number is not used to fetch subresources."""

    class MalformedPullRunner:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def __call__(self, path: str, **kwargs: Any) -> Any:
            self.calls.append(path)
            if path.endswith("/actions/runs"):
                return {"total_count": 0, "workflow_runs": []}
            if path.endswith("/pulls"):
                return [{"id": 1, "updated_at": "2026-06-06T00:00:00Z"}]
            return []  # issues, and any review/comment path

    runner = MalformedPullRunner()
    result = collect(REPO, runner=runner)

    # No /pulls/<n>/reviews call was made because the pull had no number.
    assert not any("/reviews" in c for c in runner.calls)
    assert result.counts["reviews"] == 0


def test_collect_on_empty_repo_is_noop(data_dir: Path) -> None:
    class EmptyRunner:
        def __call__(self, path: str, **kwargs: Any) -> Any:
            if path.endswith("/actions/runs"):
                return {"total_count": 0, "workflow_runs": []}
            return []

    result = collect(REPO, runner=EmptyRunner())
    assert result.counts == {
        "issues": 0,
        "pulls": 0,
        "reviews": 0,
        "review_comments": 0,
        "ci_runs": 0,
    }
    # No items means no watermark to record.
    assert read_watermark(REPO) is None
