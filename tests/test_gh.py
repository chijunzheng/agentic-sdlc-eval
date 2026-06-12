"""Tests for the gh CLI seam (subprocess wrapper around ``gh api``).

The real ``gh`` binary is never invoked here. We patch the subprocess call so
these tests stay hermetic; collector tests use a recorded-fixture runner instead
(see ``tests/test_github_collector.py``).
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest

from sdlc_eval.github.gh import GhError, run_gh_api


def _fake_run(stdout: str, returncode: int = 0, stderr: str = "") -> Any:
    def _runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    return _runner


def test_run_gh_api_parses_json_array(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [{"id": 1}, {"id": 2}]
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(payload)))
    assert run_gh_api("repos/o/r/issues") == payload


def test_run_gh_api_builds_paginated_command(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    def _runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")

    monkeypatch.setattr(subprocess, "run", _runner)
    run_gh_api("repos/o/r/issues", params={"state": "all", "sort": "updated"})

    cmd = captured["cmd"]
    assert cmd[:2] == ["gh", "api"]
    assert "repos/o/r/issues" in cmd
    # Pagination must be requested so large repos are fully walked.
    assert "--paginate" in cmd
    # Query params are passed via -f/--field flags.
    joined = " ".join(cmd)
    assert "state=all" in joined
    assert "sort=updated" in joined


def test_run_gh_api_paginate_concatenates_arrays(monkeypatch: pytest.MonkeyPatch) -> None:
    """gh --paginate with --slurp returns a list of pages; we flatten them."""
    pages = [[{"id": 1}], [{"id": 2}, {"id": 3}]]
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(pages)))
    assert run_gh_api("repos/o/r/issues", slurp=True) == [
        {"id": 1},
        {"id": 2},
        {"id": 3},
    ]


def test_run_gh_api_raises_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess, "run", _fake_run("", returncode=1, stderr="HTTP 404: Not Found")
    )
    with pytest.raises(GhError) as exc:
        run_gh_api("repos/o/missing")
    assert "404" in str(exc.value)


def test_run_gh_api_raises_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run("not json"))
    with pytest.raises(GhError):
        run_gh_api("repos/o/r")


def test_run_gh_api_empty_slurp_output_is_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty body from a paginated list endpoint means zero items."""
    monkeypatch.setattr(subprocess, "run", _fake_run("   "))
    assert run_gh_api("repos/o/r/issues", slurp=True) == []


def test_run_gh_api_empty_object_output_is_empty_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run(""))
    assert run_gh_api("repos/o/r") == {}


def test_run_gh_api_raises_when_gh_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(cmd: list[str], **kwargs: Any) -> Any:
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr(subprocess, "run", _boom)
    with pytest.raises(GhError) as exc:
        run_gh_api("repos/o/r")
    assert "gh" in str(exc.value)


def test_run_gh_api_slurp_non_list_page_is_appended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A page that is an object (not an array) is preserved, not dropped."""
    pages = [{"id": 1}, [{"id": 2}]]
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(pages)))
    assert run_gh_api("repos/o/r/issues", slurp=True) == [{"id": 1}, {"id": 2}]


def test_run_gh_api_slurp_non_list_payload_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run('{"not": "a list"}'))
    with pytest.raises(GhError) as exc:
        run_gh_api("repos/o/r/issues", slurp=True)
    assert "list of pages" in str(exc.value)
