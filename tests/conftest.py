"""Shared pytest fixtures.

Every test that touches the Event Log points the data directory at a temporary
path via the ``SDLC_EVAL_DATA_DIR`` environment variable. This keeps tests
isolated from each other and from the real on-disk log under
``~/.local/share/agentic-sdlc-eval/`` (ADR 0003).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from sdlc_eval.paths import DATA_DIR_ENV_VAR


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the Event Log at an isolated temporary data directory."""
    target = tmp_path / "data"
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(target))
    yield target
    # monkeypatch restores the environment automatically.
    os.environ.pop(DATA_DIR_ENV_VAR, None)
