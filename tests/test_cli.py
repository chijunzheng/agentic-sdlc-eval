"""Tests for the sdlc-eval CLI, focused on the status command."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from sdlc_eval import eventlog
from sdlc_eval.cli import main


def test_status_empty_log(data_dir: Path) -> None:
    result = CliRunner().invoke(main, ["status"])
    assert result.exit_code == 0
    assert "No events" in result.output


def test_status_prints_per_repo_counts(data_dir: Path) -> None:
    eventlog.append({"event_type": "session_started", "repo": "owners-manual", "session_id": "s1"})
    eventlog.append({"event_type": "session_started", "repo": "owners-manual", "session_id": "s2"})
    eventlog.append(
        {"event_type": "session_started", "repo": "agentic-sdlc-eval", "session_id": "s3"}
    )

    result = CliRunner().invoke(main, ["status"])
    assert result.exit_code == 0
    assert "owners-manual" in result.output
    assert "agentic-sdlc-eval" in result.output
    # Counts appear next to their repos.
    assert "2" in result.output
    assert "1" in result.output


def test_status_prints_total(data_dir: Path) -> None:
    eventlog.append({"event_type": "a", "repo": "r", "session_id": "s1"})
    eventlog.append({"event_type": "b", "repo": "r", "session_id": "s2"})
    eventlog.append({"event_type": "c", "repo": "r", "session_id": "s3"})

    result = CliRunner().invoke(main, ["status"])
    assert result.exit_code == 0
    assert "3" in result.output


def test_status_shows_attribution_rate(data_dir: Path) -> None:
    eventlog.append(
        {"event_type": "a", "repo": "r", "session_id": "s1", "attributed": True, "issue": 14}
    )
    eventlog.append(
        {"event_type": "b", "repo": "r", "session_id": "s2", "attributed": True, "issue": 7}
    )
    eventlog.append(
        {"event_type": "c", "repo": "r", "session_id": "s3", "attributed": False}
    )

    result = CliRunner().invoke(main, ["status"])
    assert result.exit_code == 0
    assert "Attribution" in result.output
    # 2 of 3 attributed.
    assert "2/3" in result.output
    assert "66.7%" in result.output


def test_status_attribution_rate_handles_empty_log(data_dir: Path) -> None:
    """No events → no division-by-zero; status still exits cleanly."""
    result = CliRunner().invoke(main, ["status"])
    assert result.exit_code == 0
    assert "No events" in result.output
