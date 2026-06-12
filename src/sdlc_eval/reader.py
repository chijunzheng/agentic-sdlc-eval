"""Read the Event Log back.

These are simple projections over the append-only JSONL. For the walking
skeleton we only need per-repo event counts; richer projections (Issue
Attempts, Features) land in later waves and will move to DuckDB (ADR 0003).

The repo label is read from each event's ``repo`` field — not from the
directory name — so a repo recorded as ``owner/name`` reads back under its
original label even though the on-disk directory is flattened.
"""

from __future__ import annotations

import json
from collections import Counter

from sdlc_eval.eventlog import LOG_FILENAME
from sdlc_eval.paths import events_dir


def count_events_by_repo() -> dict[str, int]:
    """Return a mapping of repo label to event count across the Event Log."""
    root = events_dir()
    if not root.exists():
        return {}

    counts: Counter[str] = Counter()
    for log_path in sorted(root.glob(f"*/{LOG_FILENAME}")):
        with log_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                counts[str(event["repo"])] += 1

    return dict(counts)
