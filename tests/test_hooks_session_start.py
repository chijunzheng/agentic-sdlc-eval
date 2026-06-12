"""Tests for the SessionStart hook adapter.

The hook reads a Claude Code SessionStart payload from stdin and appends a
``session_started`` event to the Event Log. It must never raise into the host
session: any failure is swallowed and reported via a non-fatal return.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdlc_eval import eventlog
from sdlc_eval.hooks.session_start import handle_session_start
from sdlc_eval.reader import count_events_by_repo


def test_handle_emits_session_started_event(data_dir: Path) -> None:
    payload = {
        "session_id": "sess-123",
        "cwd": "/work/owners-manual",
        "hook_event_name": "SessionStart",
    }
    stamped = handle_session_start(payload)

    assert stamped is not None
    assert stamped["event_type"] == "session_started"
    assert stamped["session_id"] == "sess-123"
    assert stamped["repo"] == "owners-manual"
    assert stamped["source"] == "hook"


def test_handle_writes_to_event_log(data_dir: Path) -> None:
    handle_session_start(
        {"session_id": "s", "cwd": "/work/my-repo", "hook_event_name": "SessionStart"}
    )
    assert count_events_by_repo() == {"my-repo": 1}


def test_handle_derives_repo_from_cwd_basename(data_dir: Path) -> None:
    stamped = handle_session_start(
        {"session_id": "s", "cwd": "/a/b/c/agentic-sdlc-eval"}
    )
    assert stamped is not None
    assert stamped["repo"] == "agentic-sdlc-eval"


def test_handle_records_source_field(data_dir: Path) -> None:
    """Auto-Capture (Layer 0) events are tagged as hook-sourced."""
    stamped = handle_session_start({"session_id": "s", "cwd": "/x/repo"})
    assert stamped is not None
    assert stamped["source"] == "hook"


def test_handle_returns_none_and_does_not_raise_on_missing_session_id(
    data_dir: Path,
) -> None:
    """A malformed payload must not crash the host session."""
    result = handle_session_start({"cwd": "/x/repo"})
    assert result is None
    assert count_events_by_repo() == {}


def test_handle_returns_none_on_missing_cwd(data_dir: Path) -> None:
    result = handle_session_start({"session_id": "s"})
    assert result is None
    assert count_events_by_repo() == {}


def test_handle_uses_repo_field_when_present(data_dir: Path) -> None:
    """An explicit repo in the payload overrides cwd derivation."""
    stamped = handle_session_start(
        {"session_id": "s", "cwd": "/tmp/checkout", "repo": "chijunzheng/owners-manual"}
    )
    assert stamped is not None
    assert stamped["repo"] == "chijunzheng/owners-manual"


def test_handle_swallows_append_failures(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An append failure must not propagate out of the hook."""

    def _boom(_event: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(eventlog, "append", _boom)
    result = handle_session_start({"session_id": "s", "cwd": "/x/repo"})
    assert result is None


def test_handle_passes_through_known_workflow_fields(data_dir: Path) -> None:
    stamped = handle_session_start(
        {
            "session_id": "s",
            "cwd": "/x/repo",
            "source": "hook",
        }
    )
    log_path = data_dir / "events" / "repo" / "events.jsonl"
    written = json.loads(log_path.read_text().splitlines()[0])
    assert written["session_id"] == "s"
    assert stamped is not None
