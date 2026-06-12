"""Tests for the ``sdlc-eval collect`` CLI subcommand.

The network is never touched: ``collect`` is patched to a stub that records its
argument and returns a canned :class:`CollectResult`. These tests pin the CLI
wiring (argument plumbing, output, exit codes), not the collector internals,
which are covered by ``tests/test_github_collector.py``.
"""

from __future__ import annotations

from click.testing import CliRunner

from sdlc_eval import cli
from sdlc_eval.github.collector import CollectResult


def test_collect_requires_repo_argument() -> None:
    result = CliRunner().invoke(cli.main, ["collect"])
    assert result.exit_code != 0
    assert "REPO" in result.output or "repo" in result.output.lower()


def test_collect_invokes_collector_with_repo(monkeypatch) -> None:
    seen: dict[str, str] = {}

    def fake_collect(repo: str) -> CollectResult:
        seen["repo"] = repo
        return CollectResult(
            repo=repo,
            counts={
                "issues": 3,
                "pulls": 2,
                "reviews": 5,
                "review_comments": 4,
                "ci_runs": 6,
            },
            watermark="2026-06-06T15:00:00Z",
        )

    monkeypatch.setattr(cli, "collect", fake_collect)
    result = CliRunner().invoke(cli.main, ["collect", "owner/name"])

    assert result.exit_code == 0
    assert seen["repo"] == "owner/name"


def test_collect_prints_per_entity_counts(monkeypatch) -> None:
    def fake_collect(repo: str) -> CollectResult:
        return CollectResult(
            repo=repo,
            counts={
                "issues": 3,
                "pulls": 2,
                "reviews": 5,
                "review_comments": 4,
                "ci_runs": 6,
            },
            watermark="2026-06-06T15:00:00Z",
        )

    monkeypatch.setattr(cli, "collect", fake_collect)
    result = CliRunner().invoke(cli.main, ["collect", "owner/name"])

    assert result.exit_code == 0
    for entity in ("issues", "pulls", "reviews", "review_comments", "ci_runs"):
        assert entity in result.output
    assert "owner/name" in result.output


def test_collect_reports_gh_failure_as_nonzero_exit(monkeypatch) -> None:
    from sdlc_eval.github.gh import GhError

    def fake_collect(repo: str) -> CollectResult:
        raise GhError("gh api repos/owner/name/issues failed (exit 1): HTTP 404")

    monkeypatch.setattr(cli, "collect", fake_collect)
    result = CliRunner().invoke(cli.main, ["collect", "owner/name"])

    assert result.exit_code != 0
    assert "404" in result.output or "failed" in result.output.lower()
