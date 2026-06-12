"""Tests for data-directory resolution (ADR 0003)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdlc_eval.paths import (
    DATA_DIR_ENV_VAR,
    events_dir,
    repo_events_dir,
    resolve_data_dir,
)


def test_default_data_dir_is_under_local_share(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default lives under ~/.local/share, outside any cloud-synced path."""
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)
    resolved = resolve_data_dir()
    expected = Path.home() / ".local" / "share" / "agentic-sdlc-eval"
    assert resolved == expected


def test_default_data_dir_is_not_cloud_synced(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default must not sit inside a Google Drive / iCloud synced tree."""
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)
    resolved = str(resolve_data_dir())
    assert "CloudStorage" not in resolved
    assert "Google Drive" not in resolved
    assert "My Drive" not in resolved


def test_env_var_overrides_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SDLC_EVAL_DATA_DIR overrides the default (needed for test isolation)."""
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(tmp_path / "custom"))
    assert resolve_data_dir() == tmp_path / "custom"


def test_events_dir_is_under_data_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(tmp_path))
    assert events_dir() == tmp_path / "events"


def test_repo_events_dir_namespaces_by_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(tmp_path))
    assert repo_events_dir("owners-manual") == tmp_path / "events" / "owners-manual"


def test_repo_events_dir_sanitizes_slashes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A repo given as owner/name must not create nested directories."""
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(tmp_path))
    resolved = repo_events_dir("chijunzheng/agentic-sdlc-eval")
    assert resolved.parent == tmp_path / "events"
    assert "/" not in resolved.name
