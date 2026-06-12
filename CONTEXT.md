# agentic-sdlc-eval

One measurement substrate for agentic SDLC workflows, usable in two modes:
**Telemetry Mode** (instrument real work on real repos) and **Benchmark Mode**
(same instrumentation, controlled task assignment). Goal: quantify the cost,
quality, and reliability of AI-coded work from idea to merge — across workflow
versions first, and eventually across coding agents (Claude Code, Codex, …).

## Language

**Telemetry Mode**:
Measurement collected from real work as a side effect of doing it; tasks arrive uncontrolled, every merge is real.
_Avoid_: "observability project" (it's one mode, not the identity)

**Benchmark Mode**:
The same instrumentation with deliberate assignment of matched Task Specs to workflow versions; attempts are ephemeral and never merge to main.
_Avoid_: "the eval" (overloaded)

**Workflow Version**:
An identifiable configuration of the SDLC skill chain (e.g., `A` = grill→PRD→issues→TDD→Codex review→merge; `B` = A + red-team, ADRs, test-critic, stronger DoD). Recorded as two fields on every event: a declared **Workflow Alias** and a computed **Workflow Fingerprint**.
_Avoid_: "the workflow" (unversioned), "new/old process"

**Workflow Alias**:
The human-declared version label (`A`, `B`, …) asserted once at Feature start and inherited by its Issue Attempts. What analyses group by.
_Avoid_: version (alone)

**Workflow Fingerprint**:
An auto-computed hash of the skill/hook/agent files in effect at attempt start. Audits whether the Alias told the truth — a fingerprint change under a stable alias is *drift*, surfaced in reports as a finding.
_Avoid_: checksum, config hash

**Feature**:
One PRD lifecycle — grill → PRD → issues → all issues merged — executed under exactly one Workflow Version. The experiment unit in Telemetry Mode.
_Avoid_: epic, project

**Issue Attempt**:
One execution of an issue (or Task Spec) from picked-up to scored PR — the atomic measured unit in both modes.
_Avoid_: run (the handoff doc's overloaded term)

**Task Spec**:
A frozen issue description pinned to a repo commit, used in Benchmark Mode so the same task can be attempted N times from identical state.
_Avoid_: benchmark task, test case

**Event Log**:
The append-only stream of structured workflow events — the spine of the system; every other data source joins onto it via `(repo, issue#, session_id)`.
_Avoid_: trace, log file (both mean other things here)

**Auto-Capture (Layer 0)**:
Events inferred mechanically by distributable hooks + OTel + the GitHub collector; requires no changes to anyone's skills. What open-source adopters get on install.
_Avoid_: "the plugin" (that's its packaging, not the concept)

**Explicit Emission (Layer 1)**:
Opt-in gold-grade events emitted by workflow skills via the `emit` CLI (e.g., a review finding from codex-review-gate). Perfect attribution; only available where skills cooperate.
_Avoid_: manual logging

**Scorecard**:
The per-attempt set of mechanical metrics, reported as per-dimension distributions grouped by Workflow Alias. Two families: **Process Metrics** (repair loops, CI failures, interventions, cost, cycle time) and **Product Metrics** (review findings, coverage delta, mutation score on diff, static-quality deltas, security/dependency deltas). Never collapsed into a weighted composite.
_Avoid_: score (singular), rubric (that's the future judge tier)

**Layer-0 Rule**:
Every Scorecard metric must be *definable* from Auto-Capture sources alone (GitHub API, OTel, hooks). Explicit Emission may refine a metric (e.g., validated severity on review findings) but may never define one.
_Avoid_: treating skill-emitted data as required

**Langfuse Mirror**:
An optional exporter that projects Issue Attempts into Langfuse for trace viewing and demos. Read-side only — never the source of truth, never load-bearing for scoring.
_Avoid_: "the Langfuse backend"

**The Lab**:
`orchestration-bench` — stays a separate project. Measures the *agent-capability* axis (synthetic terminal tasks, Docker, minutes, no GitHub/human); this project measures the *SDLC-process* axis (issues → PRs → merge, human-in-loop).
_Avoid_: conflating the two axes

## Relationships

- A **Feature** is executed under exactly one **Workflow Version** and decomposes into many **Issue Attempts**
- In Telemetry Mode, an issue has exactly **one** Issue Attempt and its PR really merges
- In Benchmark Mode, a **Task Spec** has **N** Issue Attempts per Workflow Version, each from a fresh checkout, scored then discarded
- Workflow comparison = aggregation of Issue-Attempt and Feature metrics grouped by **Workflow Version**

## Example dialogue

> **Dev:** "Can we re-run issue #14 under Workflow B to compare?"
> **Domain expert:** "Not in **Telemetry Mode** — #14 merged; it ran once, tagged with its Feature's Workflow Version. If you want a head-to-head, freeze it as a **Task Spec** and run fresh **Issue Attempts** in **Benchmark Mode** — those never touch main."

## Flagged ambiguities

- "run" (ChatGPT handoff) attached one `run_id` to everything — **resolved**: split into **Feature** (experiment unit) and **Issue Attempt** (measurement unit).
- Identity was provisionally narrowed to "telemetry, NOT benchmark" early in this session — **corrected by Jason**: both, one substrate with two modes (see ADR 0001).
