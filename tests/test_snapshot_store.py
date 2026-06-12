"""Tests for the snapshot store: per-entity JSONL files + per-repo watermark."""

from __future__ import annotations

from pathlib import Path

from sdlc_eval.github.store import (
    read_snapshot,
    read_watermark,
    upsert_snapshot,
    write_watermark,
)


def test_read_missing_snapshot_is_empty(data_dir: Path) -> None:
    assert read_snapshot("o/r", "issues") == []


def test_upsert_then_read_round_trips(data_dir: Path) -> None:
    records = [{"id": 1, "title": "a"}, {"id": 2, "title": "b"}]
    upsert_snapshot("o/r", "issues", records)
    assert read_snapshot("o/r", "issues") == records


def test_upsert_appends_new_records(data_dir: Path) -> None:
    upsert_snapshot("o/r", "issues", [{"id": 1, "title": "a"}])
    upsert_snapshot("o/r", "issues", [{"id": 2, "title": "b"}])
    by_id = {r["id"]: r for r in read_snapshot("o/r", "issues")}
    assert set(by_id) == {1, 2}


def test_upsert_replaces_existing_record_by_id(data_dir: Path) -> None:
    upsert_snapshot("o/r", "issues", [{"id": 1, "title": "old"}])
    upsert_snapshot("o/r", "issues", [{"id": 1, "title": "new"}])
    records = read_snapshot("o/r", "issues")
    assert len(records) == 1
    assert records[0]["title"] == "new"


def test_upsert_is_immutable_for_caller(data_dir: Path) -> None:
    """Upserting must not mutate the caller's record list or dicts."""
    original = [{"id": 1, "title": "a"}]
    upsert_snapshot("o/r", "issues", original)
    assert original == [{"id": 1, "title": "a"}]


def test_upsert_preserves_insertion_order(data_dir: Path) -> None:
    upsert_snapshot("o/r", "issues", [{"id": 3}, {"id": 1}, {"id": 2}])
    upsert_snapshot("o/r", "issues", [{"id": 1, "v": "updated"}])
    ids = [r["id"] for r in read_snapshot("o/r", "issues")]
    # Existing record updated in place keeps its slot; no reordering.
    assert ids == [3, 1, 2]


def test_snapshots_namespaced_per_repo(data_dir: Path) -> None:
    upsert_snapshot("o/r1", "issues", [{"id": 1}])
    upsert_snapshot("o/r2", "issues", [{"id": 9}])
    assert read_snapshot("o/r1", "issues") == [{"id": 1}]
    assert read_snapshot("o/r2", "issues") == [{"id": 9}]


def test_read_snapshot_ignores_blank_lines(data_dir: Path) -> None:
    from sdlc_eval.paths import repo_snapshots_dir

    upsert_snapshot("o/r", "issues", [{"id": 1}])
    path = repo_snapshots_dir("o/r") / "issues.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n")  # a stray blank line must not crash the reader
    assert read_snapshot("o/r", "issues") == [{"id": 1}]


def test_watermark_missing_is_none(data_dir: Path) -> None:
    assert read_watermark("o/r") is None


def test_watermark_round_trips(data_dir: Path) -> None:
    write_watermark("o/r", "2026-06-10T00:00:00Z")
    assert read_watermark("o/r") == "2026-06-10T00:00:00Z"


def test_watermark_is_per_repo(data_dir: Path) -> None:
    write_watermark("o/r1", "2026-06-10T00:00:00Z")
    assert read_watermark("o/r2") is None
