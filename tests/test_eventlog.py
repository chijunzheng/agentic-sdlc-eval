"""Tests for the eventlog deep module: the single append() entrypoint.

The eventlog module is the spine of the system. Its public surface is one
function, ``append(event)``, which stamps an envelope and appends one JSON
line (O_APPEND) to the Event Log under the local data directory (ADR 0003).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sdlc_eval import eventlog
from sdlc_eval.eventlog import SCHEMA_VERSION


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


# --- envelope correctness -------------------------------------------------


def test_append_stamps_required_envelope_fields(data_dir: Path) -> None:
    stamped = eventlog.append(
        {"event_type": "session_started", "repo": "owners-manual", "session_id": "abc"}
    )
    for field in ("timestamp", "schema_version", "event_type", "repo", "session_id"):
        assert field in stamped


def test_append_sets_schema_version(data_dir: Path) -> None:
    stamped = eventlog.append(
        {"event_type": "session_started", "repo": "r", "session_id": "s"}
    )
    assert stamped["schema_version"] == SCHEMA_VERSION


def test_append_stamps_utc_iso8601_timestamp(data_dir: Path) -> None:
    stamped = eventlog.append(
        {"event_type": "session_started", "repo": "r", "session_id": "s"}
    )
    parsed = datetime.fromisoformat(stamped["timestamp"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == UTC.utcoffset(None)


def test_append_does_not_mutate_caller_event(data_dir: Path) -> None:
    """Immutability: the caller's dict must be left untouched."""
    event = {"event_type": "session_started", "repo": "r", "session_id": "s"}
    eventlog.append(event)
    assert event == {"event_type": "session_started", "repo": "r", "session_id": "s"}


def test_append_preserves_workflow_fields(data_dir: Path) -> None:
    """Workflow fields (alias, fingerprint, issue) pass through when present."""
    stamped = eventlog.append(
        {
            "event_type": "session_started",
            "repo": "r",
            "session_id": "s",
            "workflow_alias": "B",
            "workflow_fingerprint": "deadbeef",
            "issue": 14,
        }
    )
    assert stamped["workflow_alias"] == "B"
    assert stamped["workflow_fingerprint"] == "deadbeef"
    assert stamped["issue"] == 14


def test_append_provided_timestamp_is_not_overwritten(data_dir: Path) -> None:
    """A caller-supplied timestamp (e.g. replay) is respected."""
    fixed = "2026-06-12T00:00:00+00:00"
    stamped = eventlog.append(
        {
            "event_type": "session_started",
            "repo": "r",
            "session_id": "s",
            "timestamp": fixed,
        }
    )
    assert stamped["timestamp"] == fixed


# --- validation -----------------------------------------------------------


def test_append_rejects_missing_event_type(data_dir: Path) -> None:
    with pytest.raises(ValueError):
        eventlog.append({"repo": "r", "session_id": "s"})


def test_append_rejects_missing_repo(data_dir: Path) -> None:
    with pytest.raises(ValueError):
        eventlog.append({"event_type": "session_started", "session_id": "s"})


def test_append_rejects_non_mapping_event(data_dir: Path) -> None:
    with pytest.raises(TypeError):
        eventlog.append("not-a-dict")  # type: ignore[arg-type]


# --- append behavior ------------------------------------------------------


def test_append_writes_jsonl_under_repo_dir(data_dir: Path) -> None:
    eventlog.append(
        {"event_type": "session_started", "repo": "owners-manual", "session_id": "s"}
    )
    log_path = data_dir / "events" / "owners-manual" / "events.jsonl"
    assert log_path.exists()
    lines = _read_lines(log_path)
    assert len(lines) == 1
    assert lines[0]["event_type"] == "session_started"


def test_append_is_append_only(data_dir: Path) -> None:
    """Two appends produce two lines; the first is never overwritten."""
    eventlog.append({"event_type": "a", "repo": "r", "session_id": "s1"})
    eventlog.append({"event_type": "b", "repo": "r", "session_id": "s2"})
    log_path = data_dir / "events" / "r" / "events.jsonl"
    lines = _read_lines(log_path)
    assert [line["event_type"] for line in lines] == ["a", "b"]


def test_append_writes_one_line_per_event(data_dir: Path) -> None:
    """Each event is exactly one newline-terminated line (no embedded \\n)."""
    eventlog.append(
        {
            "event_type": "session_started",
            "repo": "r",
            "session_id": "s",
            "note": "multi\nline\nvalue",
        }
    )
    log_path = data_dir / "events" / "r" / "events.jsonl"
    raw = log_path.read_text()
    assert raw.endswith("\n")
    assert raw.count("\n") == 1


def test_append_separates_repos(data_dir: Path) -> None:
    eventlog.append({"event_type": "a", "repo": "repo-one", "session_id": "s"})
    eventlog.append({"event_type": "b", "repo": "repo-two", "session_id": "s"})
    assert (data_dir / "events" / "repo-one" / "events.jsonl").exists()
    assert (data_dir / "events" / "repo-two" / "events.jsonl").exists()


def test_append_raises_on_short_write(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partial os.write (disk full, quota, interrupt) must not report success.

    A short write leaves a torn line in the Event Log; append() must surface
    it as a failure rather than returning the stamped event as if persisted.
    """

    def _short_write(fd: int, payload: bytes) -> int:
        return len(payload) - 1

    monkeypatch.setattr(eventlog.os, "write", _short_write)
    with pytest.raises(OSError, match="short write"):
        eventlog.append({"event_type": "a", "repo": "r", "session_id": "s"})


def test_append_wraps_write_failures_as_oserror(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A filesystem failure surfaces as an OSError naming the repo dir."""

    def _boom(*_args: object, **_kwargs: object) -> int:
        raise OSError("disk full")

    monkeypatch.setattr(eventlog.os, "open", _boom)
    with pytest.raises(OSError, match="failed to append event to Event Log"):
        eventlog.append({"event_type": "a", "repo": "r", "session_id": "s"})
