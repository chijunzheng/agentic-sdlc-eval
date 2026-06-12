"""Tests for reading the Event Log back (per-repo counts)."""

from __future__ import annotations

from pathlib import Path

from sdlc_eval import eventlog
from sdlc_eval.reader import attribution_rate, count_events_by_repo


def test_counts_empty_log_is_empty(data_dir: Path) -> None:
    assert count_events_by_repo() == {}


def test_counts_single_repo(data_dir: Path) -> None:
    eventlog.append({"event_type": "session_started", "repo": "r", "session_id": "s1"})
    eventlog.append({"event_type": "session_started", "repo": "r", "session_id": "s2"})
    assert count_events_by_repo() == {"r": 2}


def test_counts_multiple_repos(data_dir: Path) -> None:
    eventlog.append({"event_type": "a", "repo": "repo-one", "session_id": "s"})
    eventlog.append({"event_type": "b", "repo": "repo-one", "session_id": "s"})
    eventlog.append({"event_type": "c", "repo": "repo-two", "session_id": "s"})
    assert count_events_by_repo() == {"repo-one": 2, "repo-two": 1}


def test_counts_preserve_slashed_repo_names(data_dir: Path) -> None:
    """A repo recorded as owner/name reads back under its original label."""
    eventlog.append(
        {"event_type": "a", "repo": "chijunzheng/agentic-sdlc-eval", "session_id": "s"}
    )
    assert count_events_by_repo() == {"chijunzheng/agentic-sdlc-eval": 1}


def test_counts_ignore_blank_lines(data_dir: Path) -> None:
    eventlog.append({"event_type": "a", "repo": "r", "session_id": "s"})
    log_path = data_dir / "events" / "r" / "events.jsonl"
    with log_path.open("a") as handle:
        handle.write("\n")  # a stray blank line must not be counted
    assert count_events_by_repo() == {"r": 1}


# --- attribution rate (issue #3) -----------------------------------------


def test_attribution_rate_empty_log(data_dir: Path) -> None:
    """No events → (0 attributed, 0 total); callers handle the zero case."""
    assert attribution_rate() == (0, 0)


def test_attribution_rate_counts_attributed_over_total(data_dir: Path) -> None:
    eventlog.append(
        {"event_type": "a", "repo": "r", "session_id": "s", "attributed": True, "issue": 14}
    )
    eventlog.append(
        {"event_type": "b", "repo": "r", "session_id": "s", "attributed": True, "issue": 7}
    )
    eventlog.append(
        {"event_type": "c", "repo": "r", "session_id": "s", "attributed": False}
    )
    assert attribution_rate() == (2, 3)


def test_attribution_rate_treats_missing_flag_as_unattributed(data_dir: Path) -> None:
    """Legacy events without an attributed flag count toward total, not attributed."""
    eventlog.append({"event_type": "legacy", "repo": "r", "session_id": "s"})
    eventlog.append(
        {"event_type": "new", "repo": "r", "session_id": "s", "attributed": True, "issue": 1}
    )
    assert attribution_rate() == (1, 2)
