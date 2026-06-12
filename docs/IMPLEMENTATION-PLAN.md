# Implementation plan

**Last updated**: 2026-06-12
**Open issues**: 10 (+ #1 PRD tracking issue) — **Closed**: 0 — **Ready now**: 1

## Recently closed

None yet — greenfield queue.

## Wave structure

Each row is one wave (= topological-sort level). Issues within a wave have no dependency between them. #1 (PRD) is the tracking parent and is excluded from waves.

| Wave | Issues | Unblocks | Notes |
|---|---|---|---|
| 0 (foundation) | #2 | Wave 1 | The walking skeleton — everything depends on it |
| 1 | #3, #4, #7 | Wave 2 | Three independent deep modules |
| 2 | #5 | Wave 3 | Hook suite, needs attribution (#3) + fingerprints (#4) |
| 3 | #6 [HITL], #8 | Wave 4 | #6 starts the baseline; #8 needs hooks (#5) + snapshots (#7) |
| 4 | #9, #10 | Wave 5 | Metric layers over projections (#8) |
| 5 | #11 | — | Terminal: the v0.1 Markdown Scorecard |

Per-issue detail, grouped by wave:

### Wave 0

- **#2 Walking skeleton: eventlog appends to the Event Log and status reads it back** — Blocked by: none. HITL: no. Touches: project scaffold (uv/pytest), eventlog module, SessionStart hook, status CLI.

### Wave 1

- **#3 context_resolver: stamp events with repo and issue attribution** — Blocked by: #2. HITL: no. Touches: context_resolver module, event envelope fields, status (attribution rate).
- **#4 fingerprinter: Workflow Alias registry and Fingerprint stamping** — Blocked by: #2. HITL: no. Touches: fingerprinter module, alias registry file, event envelope fields, status.
- **#7 github_collector: incremental reviewer-agnostic snapshots** — Blocked by: #2. HITL: no. Touches: github_collector module, collect CLI command, snapshot storage layout.

### Wave 2

- **#5 Layer-0 hook suite: interventions, session boundaries, PR lifecycle** — Blocked by: #3, #4. HITL: no. Touches: hook adapter scripts, hook config.

### Wave 3

- **#6 init command and pilot rollout: baseline starts on both repos** — Blocked by: #5. **HITL: yes.** Touches: init CLI command, both pilot repos' settings.
- **#8 Projections: Issue Attempts, Features, drift and attribution-gap relations** — Blocked by: #5, #7. HITL: no. Touches: projections module (DuckDB views).

### Wave 4

- **#9 Cost capture: per-session token cost joined to Issue Attempts** — Blocked by: #2 (closed-by-then), #8. HITL: no. Touches: cost capture path, projections join.
- **#10 Scorecard projections: process and review metrics** — Blocked by: #8. HITL: no. Touches: projections module (metric views).

### Wave 5

- **#11 report command: Markdown Scorecard grouped by Workflow Alias** — Blocked by: #9, #10. HITL: no. Touches: report CLI command, Markdown rendering.

## Currently ready

Issues with zero open blockers as of 2026-06-12:

1. **#2 Walking skeleton: eventlog appends to the Event Log and status reads it back** — Recommended next. Sole ready issue; head of the critical path; unblocks three parallel Wave-1 issues.

## Critical path

Longest remaining chain from a ready-now issue to closure:

`#2 → #3 → #5 → #8 → #9 → #11`

**Length**: 6 issues. (#4 substitutes for #3, and #10 for #9, at equal length.)

## HITL pause points

Issues that require human judgment (not sub-agent-dispatchable):

- **#6 init command and pilot rollout** — Why: installs hooks into owners-manual's settings and requires a human to verify, after a day of real work, that both pilots emit events with healthy attribution. Baseline accrual officially starts here.

## Parallelism windows

For each currently-ready issue, what closing it unblocks:

- **Closing #2 unblocks**: #3, #4, #7 (Wave 1). Parallel-safe pairs: (#3, #7) and (#4, #7) — #7 is an independent module. **Caution on (#3, #4)**: both extend the event envelope and the status command; expect merge friction if dispatched simultaneously.

## Dispatch prompt

When dispatching the next issue, populate the template in
`~/.claude/skills/to-implementation/DISPATCH-TEMPLATE.md` and pass it to a
`tdd-guide` sub-agent. For #2 (net-new code, no prior art): area = "project
scaffold + eventlog + status walking skeleton"; bootloader = issue body,
CONTEXT.md, ADRs 0001–0004; no prior-art file paths.
