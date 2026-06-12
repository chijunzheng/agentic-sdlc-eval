# Objective-only v1 scorecard, no weighted composite, Layer-0 definability rule

The v1 Scorecard is mechanical metrics only, reported as per-dimension
distributions grouped by Workflow Alias — there is deliberately no single
weighted score. Composite weights and cross-unit normalization are arbitrary
choices that change meaning when revised and bury the dimensional story ("B:
−40% review findings, +2.1× cost") that is the actual finding. Product quality
is measured directly via mutation score on the diff (test meaningfulness),
static-quality deltas, and security/dependency deltas; post-merge defect
attribution (SZZ/reverts) was considered and deferred entirely from v1. An LLM
judge tier (requirement coverage, maintainability) may be added later only
with a pinned, cross-family judge model and a human-agreement calibration step.
Binding rule: every metric must be definable from Layer-0 sources (GitHub API,
OTel, hooks) so the open-sourced tool works without anyone editing their
skills; Layer-1 emissions refine metrics but never define them.
