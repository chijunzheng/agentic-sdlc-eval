"""The github_collector deep module: incremental, reviewer-agnostic snapshots.

``collect(repo)`` pulls issues, pull requests, reviews, review comments, and CI
runs for a repo via the ``gh`` CLI into JSON snapshot files under the data dir,
fetching only items updated since the last sync watermark (ADR 0003). Snapshots
are reviewer-agnostic per the Layer-0 Rule: their shape is identical whether a
review's author is a bot (Codex, CodeRabbit, Copilot) or a human.
"""

from __future__ import annotations

from sdlc_eval.github.collector import CollectResult, collect

__all__ = ["collect", "CollectResult"]
