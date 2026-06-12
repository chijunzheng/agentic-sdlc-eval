# JSONL event log queried by DuckDB; Langfuse is a read-only mirror

Events are append-only JSONL under `~/.local/share/agentic-sdlc-eval/`
(deliberately outside Google-Drive-synced paths — sync corrupts mutable data
files). DuckDB queries the JSONL and GitHub snapshots in place; Issue Attempts,
Features, and scorecards are projections, so schema evolution is a re-projection
rather than a migration. An optional exporter mirrors attempts into Langfuse for
its trace UI, but Langfuse is never the source of truth and nothing may depend
on it for scoring. Rejected: SQLite as primary (write-lock contention across
concurrent hook writers; Drive-sync hazard) and Langfuse-first (forces SDLC
entities into trace semantics; requires every adopter to run Langfuse).
