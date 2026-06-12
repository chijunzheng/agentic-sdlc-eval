"""Concurrency test: parallel-process appends must not interleave or corrupt.

ADR 0003 chose JSONL with O_APPEND over SQLite specifically to survive
concurrent hook writers. This test forks many real processes that each append
several events to the same repo log, then asserts every line is intact JSON and
the total count is exactly right.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sdlc_eval import eventlog
from sdlc_eval.paths import DATA_DIR_ENV_VAR

WRITERS = 8
EVENTS_PER_WRITER = 50
REPO = "concurrent-repo"


def _writer(args: tuple[str, int]) -> None:
    data_dir, writer_id = args
    os.environ[DATA_DIR_ENV_VAR] = data_dir
    for i in range(EVENTS_PER_WRITER):
        eventlog.append(
            {
                "event_type": "session_started",
                "repo": REPO,
                "session_id": f"w{writer_id}-e{i}",
                # A wide payload increases the chance of catching interleaving
                # if the write were not atomic.
                "payload": "x" * 200,
            }
        )


def test_concurrent_appends_are_not_interleaved(
    data_dir: Path, monkeypatch: object
) -> None:
    # ProcessPoolExecutor spawns fresh processes; pass the data dir explicitly
    # because env mutations in the parent do not propagate to spawned children
    # on macOS (spawn start method).
    with ProcessPoolExecutor(max_workers=WRITERS) as pool:
        list(pool.map(_writer, [(str(data_dir), w) for w in range(WRITERS)]))

    log_path = data_dir / "events" / REPO / "events.jsonl"
    raw_lines = log_path.read_text().splitlines()

    # No corrupt or interleaved lines: every line parses as JSON on its own.
    parsed = [json.loads(line) for line in raw_lines]

    # No lines lost or duplicated.
    assert len(parsed) == WRITERS * EVENTS_PER_WRITER

    # Every event's session_id is unique and accounted for.
    session_ids = {event["session_id"] for event in parsed}
    expected = {
        f"w{w}-e{i}" for w in range(WRITERS) for i in range(EVENTS_PER_WRITER)
    }
    assert session_ids == expected
