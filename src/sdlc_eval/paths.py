"""Data-directory resolution for the Event Log.

Per ADR 0003 the Event Log lives under ``~/.local/share/agentic-sdlc-eval/``,
deliberately outside any cloud-synced path (Drive/iCloud sync corrupts mutable
data files). The location is overridable via the ``SDLC_EVAL_DATA_DIR``
environment variable, which keeps tests isolated and lets adopters relocate the
log without code changes.
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR_ENV_VAR = "SDLC_EVAL_DATA_DIR"
_DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "agentic-sdlc-eval"


def resolve_data_dir() -> Path:
    """Return the root data directory, honoring the override env var."""
    override = os.environ.get(DATA_DIR_ENV_VAR)
    if override:
        return Path(override)
    return _DEFAULT_DATA_DIR


def events_dir() -> Path:
    """Return the directory holding per-repo Event Log subdirectories."""
    return resolve_data_dir() / "events"


def _sanitize_repo(repo: str) -> str:
    """Flatten a repo identifier into a single safe directory name.

    A repo may be given as ``owner/name``; collapse the separator so it never
    creates nested directories or escapes the events root.
    """
    return repo.replace("/", "__").replace(os.sep, "__")


def repo_events_dir(repo: str) -> Path:
    """Return the Event Log directory for a single repo."""
    return events_dir() / _sanitize_repo(repo)
