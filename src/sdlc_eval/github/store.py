"""Persistence for GitHub snapshots and the per-repo sync watermark.

Each entity type (``issues``, ``pulls``, ``reviews``, ``review_comments``,
``ci_runs``) is stored as one JSONL file under the repo's snapshot directory,
one record per line. Incremental collection *upserts* by the record ``id``:
records present in a new batch replace any existing record with the same id,
records absent from the batch are preserved, and brand-new records are appended.
That makes a second ``collect`` run additive — it only needs the items GitHub
reports as changed since the watermark, yet the snapshot stays complete.

Writes are atomic (write to a temp file in the same directory, then ``rename``)
so a crash mid-write never leaves a torn snapshot — the prior snapshot survives
and the next run resumes safely.

The watermark — the high-water ``updated_at`` from the last *successful* run —
lives in ``.sync.json``. It advances only after a run completes, so a failed run
re-fetches from the previous mark rather than skipping items.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from sdlc_eval.paths import repo_snapshots_dir

WATERMARK_FILENAME = ".sync.json"
_ID_KEY = "id"


def _entity_path(repo: str, entity: str) -> Path:
    return repo_snapshots_dir(repo) / f"{entity}.jsonl"


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically via a temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def read_snapshot(repo: str, entity: str) -> list[dict[str, Any]]:
    """Return the stored records for ``entity`` in ``repo`` (empty if none)."""
    path = _entity_path(repo, entity)
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _serialize_records(records: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        json.dumps(record, ensure_ascii=False, sort_keys=False, separators=(",", ":"))
        for record in records
    ]
    return "".join(f"{line}\n" for line in lines)


def upsert_snapshot(
    repo: str, entity: str, records: Iterable[Mapping[str, Any]]
) -> int:
    """Merge ``records`` into the ``entity`` snapshot, keyed by ``id``.

    Existing records keep their position; a record whose ``id`` matches an
    incoming one is replaced in place. New records are appended in iteration
    order. Returns the count of incoming records merged.

    The caller's data is never mutated: every record is copied before storage.
    """
    existing = read_snapshot(repo, entity)
    index_by_id = {
        record[_ID_KEY]: position
        for position, record in enumerate(existing)
        if _ID_KEY in record
    }

    merged: list[dict[str, Any]] = [dict(record) for record in existing]
    incoming_count = 0
    for record in records:
        incoming_count += 1
        copy = dict(record)
        record_id = copy.get(_ID_KEY)
        if record_id is not None and record_id in index_by_id:
            merged[index_by_id[record_id]] = copy
        else:
            if record_id is not None:
                index_by_id[record_id] = len(merged)
            merged.append(copy)

    _atomic_write_text(_entity_path(repo, entity), _serialize_records(merged))
    return incoming_count


def _watermark_path(repo: str) -> Path:
    return repo_snapshots_dir(repo) / WATERMARK_FILENAME


def read_watermark(repo: str) -> str | None:
    """Return the last successful sync watermark for ``repo`` (or None)."""
    path = _watermark_path(repo)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    watermark = data.get("watermark")
    return watermark if isinstance(watermark, str) else None


def write_watermark(repo: str, watermark: str) -> None:
    """Persist the high-water ``updated_at`` for ``repo`` atomically."""
    payload = json.dumps({"watermark": watermark}, ensure_ascii=False)
    _atomic_write_text(_watermark_path(repo), payload + "\n")
