"""Tests for the `sdlc-eval hook session-start` entrypoint.

This is the command Claude Code's SessionStart hook actually runs. It reads a
JSON payload from stdin and appends a session_started event. It must always
exit 0 so a hook failure can never break the host session.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from sdlc_eval.cli import main
from sdlc_eval.reader import count_events_by_repo


def test_hook_session_start_reads_stdin_and_appends(data_dir: Path) -> None:
    payload = json.dumps(
        {"session_id": "sess-1", "cwd": "/work/owners-manual"}
    )
    result = CliRunner().invoke(main, ["hook", "session-start"], input=payload)
    assert result.exit_code == 0
    assert count_events_by_repo() == {"owners-manual": 1}


def test_hook_session_start_exits_zero_on_empty_stdin(data_dir: Path) -> None:
    result = CliRunner().invoke(main, ["hook", "session-start"], input="")
    assert result.exit_code == 0
    assert count_events_by_repo() == {}


def test_hook_session_start_exits_zero_on_malformed_json(data_dir: Path) -> None:
    result = CliRunner().invoke(main, ["hook", "session-start"], input="{not json")
    assert result.exit_code == 0
    assert count_events_by_repo() == {}
