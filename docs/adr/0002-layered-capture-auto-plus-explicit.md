# Layered capture: auto-instrumentation spine with optional explicit emission

The spine is a unified Event Log with two producer layers. Layer 0
(auto-capture): plugin-shippable Claude Code hooks + OTel + a GitHub collector
infer lifecycle events from tool calls and naming conventions (branch/commit
references like `fixes #14`) — adopters instrument nothing. Layer 1 (explicit
emission): an `emit` CLI that workflow skills may call for events no hook can
infer (review findings, red-team verdicts, test-critic results). We chose this
over skill-emitted-only because requiring skill edits would make the
open-sourced tool impractical to adopt, and over auto-only because Layer-0
cannot see the semantic signals that Workflow B's value proposition depends on.
This mirrors OpenTelemetry's auto-instrumentation + manual-spans architecture.
