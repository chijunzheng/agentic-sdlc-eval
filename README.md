# agentic-sdlc-eval

One measurement substrate for agentic SDLC workflows, usable in two modes:
**Telemetry Mode** (instrument real work on real repos) and **Benchmark Mode**
(same instrumentation, controlled task assignment). Goal: quantify the cost,
quality, and reliability of AI-coded work from idea to merge.

See [`CONTEXT.md`](CONTEXT.md) for the canonical glossary and
[`docs/adr/`](docs/adr/) for architectural decisions.

## Walking skeleton (v0.1)

The first event flows end-to-end:

1. A Claude Code **SessionStart** hook appends a `session_started` event to the
   **Event Log** (append-only JSONL).
2. `sdlc-eval status` reads the log back and prints per-repo event counts.

The Event Log lives under `~/.local/share/agentic-sdlc-eval/events/<repo>/`,
deliberately outside any cloud-synced path (see
[ADR 0003](docs/adr/0003-jsonl-duckdb-spine-langfuse-mirror.md)).

## Development

This project is managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync            # create venv and install deps
uv run pytest      # run the test suite
uv run ruff check  # lint
uv run mypy        # type check
```

## Usage

```bash
# Print per-repo event counts read from the Event Log
uv run sdlc-eval status
```
