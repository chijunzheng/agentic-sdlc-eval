# One measurement substrate, two modes; orchestration-bench stays the task-level lab

agentic-sdlc-eval is a single instrumentation substrate used in two modes:
Telemetry Mode (real work, real merges, uncontrolled tasks) and Benchmark Mode
(frozen Task Specs, fresh checkouts, ephemeral PRs, N attempts per arm). The
atomic row type in both is the Issue Attempt; the experiment unit in Telemetry
Mode is the Feature, which carries the Workflow Version. `orchestration-bench`
remains a separate project measuring a different axis — raw agent capability on
synthetic terminal tasks — and is not absorbed or deprecated.

## Considered Options

- **Telemetry-only** (benchmark delegated to orchestration-bench) — rejected:
  Terminal-Bench tasks cannot exercise PRDs, GitHub issues, or PR review loops,
  so the SDLC-level benchmark has nowhere else to live.
- **Benchmark-only** (the originating ChatGPT proposal) — rejected: pays
  benchmark-construction cost up front while ignoring the free data from real
  work, and inherits n=1 variance without the realism payoff.
- **Absorb orchestration-bench** — rejected: mixes two unrelated experimental
  setups (Docker/TB harness vs GitHub-native SDLC) in one repo.
