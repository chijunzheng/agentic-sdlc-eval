"""Tests for the SessionStart hook adapter.

The hook reads a Claude Code SessionStart payload from stdin and appends a
``session_started`` event to the Event Log. It must never raise into the host
session: any failure is swallowed and reported via a non-fatal return.
"""

from __future__ import annotations

import json
import subprocess
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


# --- attribution stamping (issue #3) --------------------------------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path: Path, remote: str, branch: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    _git(path, "remote", "add", "origin", remote)
    _git(path, "checkout", "-q", "-b", branch)
    (path / "f").write_text("x")
    _git(path, "add", "f")
    _git(path, "commit", "-q", "-m", "init")
    return path


def test_handle_stamps_attribution_fields_from_git(
    data_dir: Path, tmp_path: Path
) -> None:
    """An event in a real repo on an issue branch carries repo + issue + attributed."""
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/chijunzheng/owners-manual.git",
        branch="issue-14-thing",
    )
    stamped = handle_session_start({"session_id": "s", "cwd": str(repo)})
    assert stamped is not None
    assert stamped["repo"] == "chijunzheng/owners-manual"
    assert stamped["issue"] == 14
    assert stamped["attributed"] is True


def test_handle_flags_unattributed_event_not_dropped(
    data_dir: Path, tmp_path: Path
) -> None:
    """A convention-free branch produces an event flagged unattributed, not dropped."""
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/o/n.git",
        branch="main",
    )
    stamped = handle_session_start({"session_id": "s", "cwd": str(repo)})
    assert stamped is not None  # never dropped
    assert stamped["attributed"] is False
    assert "issue" not in stamped or stamped["issue"] is None
    assert count_events_by_repo() == {"o/n": 1}


def test_handle_non_git_cwd_is_flagged_unattributed(data_dir: Path) -> None:
    """The legacy basename path (non-git cwd) is recorded but unattributed."""
    stamped = handle_session_start({"session_id": "s", "cwd": "/work/owners-manual"})
    assert stamped is not None
    assert stamped["repo"] == "owners-manual"
    assert stamped["attributed"] is False
