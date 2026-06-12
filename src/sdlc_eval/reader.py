"""Read the Event Log back.

These are simple projections over the append-only JSONL. For the walking
skeleton we only need per-repo event counts and the attribution rate; richer
projections (Issue Attempts, Features) land in later waves and will move to
DuckDB (ADR 0003).

The repo label is read from each event's ``repo`` field — not from the
directory name — so a repo recorded as ``owner/name`` reads back under its
original label even though the on-disk directory is flattened.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from typing import Any

from sdlc_eval.eventlog import LOG_FILENAME
from sdlc_eval.paths import events_dir


def _iter_events() -> Iterator[dict[str, Any]]:
    """Yield every event in the Event Log, skipping blank lines."""
    root = events_dir()
    if not root.exists():
        return

    for log_path in sorted(root.glob(f"*/{LOG_FILENAME}")):
        with log_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)


def count_events_by_repo() -> dict[str, int]:
    """Return a mapping of repo label to event count across the Event Log."""
    counts: Counter[str] = Counter()
    for event in _iter_events():
        counts[str(event["repo"])] += 1
    return dict(counts)


def attribution_rate() -> tuple[int, int]:
    """Return ``(attributed, total)`` event counts across the Event Log.

    An event is attributed when its ``attributed`` flag is truthy (set by the
    context_resolver). Events missing the flag — e.g. older records — count
    toward the total but not toward attributed, so the rate stays honest about
    coverage. Callers handle the ``total == 0`` case.
    """
    attributed = 0
    total = 0
    for event in _iter_events():
        total += 1
        if event.get("attributed"):
            attributed += 1
    return attributed, total
