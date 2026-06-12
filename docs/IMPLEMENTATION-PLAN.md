# Implementation plan

**Last updated**: 2026-06-12 (post #2 merge)
**Open issues**: 10 (+ #1 PRD tracking issue) — **Closed**: 1 — **Ready now**: 4

## Recently closed

- #2 Walking skeleton: eventlog appends to the Event Log and status reads it back (PR #12, gated: 1 Codex finding, real, fixed)

## Wave structure

Each row is one wave (= topological-sort level). Issues within a wave have no dependency between them. #1 (PRD) is the tracking parent and is excluded from waves.

| Wave | Issues | Unblocks | Notes |
|---|---|---|---|
| 0 (ready) | #3, #4, #7, #13 | Wave 1 | All blockers closed |
| 1 | #5 | Wave 2 | Hook suite, needs #3 + #4 |
| 2 | #6 [HITL], #8 | Wave 3 | #6 starts the baseline; #8 needs #5 + #7 |
| 3 | #9, #10 | Wave 4 | Metric layers over projections (#8) |
| 4 | #11 | — | Terminal: the v0.1 Markdown Scorecard |

Per-issue detail, grouped by wave:

### Wave 0 (ready now)

- **#3 context_resolver: stamp events with repo and issue attribution** — Blocked by: none open. HITL: no. Touches: new context_resolver module, envelope fields, cli/status (attribution rate).
- **#4 fingerprinter: Workflow Alias registry and Fingerprint stamping** — Blocked by: none open. HITL: no. Touches: new fingerprinter module, registry file, envelope fields, cli/status.
- **#7 github_collector: incremental reviewer-agnostic snapshots** — Blocked by: none open. HITL: no. Touches: new github_collector module, cli (new collect subcommand), snapshot storage layout.
- **#13 reader: tolerate malformed Event Log lines instead of crashing status** — Blocked by: none open. HITL: no. Touches: reader, cli/status (malformed-line health signal). Found during PR #12 review gate.

### Wave 1

- **#5 Layer-0 hook suite** — Blocked by: #3, #4. HITL: no. Touches: hook adapters, hook config.

### Wave 2

- **#6 init command and pilot rollout** — Blocked by: #5. **HITL: yes.** Touches: init CLI, both pilot repos' settings.
- **#8 Projections: Issue Attempts, Features, drift and attribution-gap relations** — Blocked by: #5, #7. HITL: no. Touches: projections module (DuckDB views).

### Wave 3

- **#9 Cost capture** — Blocked by: #8. HITL: no. Touches: cost capture path, projections join.
- **#10 Scorecard projections: process and review metrics** — Blocked by: #8. HITL: no. Touches: projections module (metric views).

### Wave 4

- **#11 report command: Markdown Scorecard** — Blocked by: #9, #10. HITL: no. Touches: report CLI, Markdown rendering.

## Currently ready

Issues with zero open blockers as of 2026-06-12:

1. **#3 context_resolver** — Recommended next. On the critical path; with #4, gates the hook suite (#5).
2. **#7 github_collector** — Parallel-safe with #3: yes (independent module; both add a distinct cli subcommand — minor, mergeable overlap).
3. **#4 fingerprinter** — Parallel-safe with #3: **no** — both extend the event envelope and status output; expect merge friction.
4. **#13 reader tolerance** — Parallel-safe with #3: **caution** — both modify status output.

## Critical path

`#3 → #5 → #8 → #9 → #11`

**Length**: 5 issues. (#4 substitutes for #3, and #10 for #9, at equal length.)

## HITL pause points

- **#6 init command and pilot rollout** — Why: installs hooks into owners-manual's settings; human verifies after a day of real work that both pilots emit events with healthy attribution. Baseline accrual officially starts here.

## Parallelism windows

- **Closing #3 + #4 unblocks**: #5 (Wave 1).
- **Closing #7 unblocks**: nothing alone — #8 also needs #5.
- **Closing #13 unblocks**: nothing (leaf robustness issue).

## Dispatch prompt

Populate `~/.claude/skills/to-implementation/DISPATCH-TEMPLATE.md` per dispatch.
Prior art now exists: eventlog/envelope/paths/reader/cli modules and their tests
under src/sdlc_eval/ and tests/ (point sub-agents at the specific 1–5 relevant
files only).
