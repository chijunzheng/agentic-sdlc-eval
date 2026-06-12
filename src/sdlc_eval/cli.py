"""The ``sdlc-eval`` command-line interface.

For the walking skeleton this exposes a single command, ``status``, which reads
the Event Log back and prints per-repo event counts.
"""

from __future__ import annotations

import json
import sys

import click

from sdlc_eval.github import collect
from sdlc_eval.github.gh import GhError
from sdlc_eval.hooks.session_start import handle_session_start
from sdlc_eval.reader import count_events_by_repo


@click.group()
@click.version_option(package_name="agentic-sdlc-eval")
def main() -> None:
    """agentic-sdlc-eval: measure agentic SDLC workflows."""


@main.command()
def status() -> None:
    """Print per-repo event counts read from the Event Log."""
    counts = count_events_by_repo()

    if not counts:
        click.echo("No events recorded yet.")
        return

    width = max(len(repo) for repo in counts)
    click.echo("Event Log status (events per repo):")
    for repo in sorted(counts):
        click.echo(f"  {repo.ljust(width)}  {counts[repo]}")

    total = sum(counts.values())
    click.echo(f"  {'TOTAL'.ljust(width)}  {total}")


@main.command(name="collect")
@click.argument("repo")
def collect_command(repo: str) -> None:
    """Snapshot a repo's issues, PRs, reviews, comments, and CI runs.

    REPO is the ``owner/name`` identifier. Only items updated since the last
    sync watermark are fetched, so re-running is incremental. Requires the
    ``gh`` CLI to be installed and authenticated.
    """
    try:
        result = collect(repo)
    except GhError as error:
        raise click.ClickException(str(error)) from error

    click.echo(f"Collected GitHub snapshots for {result.repo}:")
    width = max(len(entity) for entity in result.counts)
    for entity in result.counts:
        click.echo(f"  {entity.ljust(width)}  {result.counts[entity]}")
    if result.watermark is not None:
        click.echo(f"  watermark: {result.watermark}")


@main.group()
def hook() -> None:
    """Claude Code hook entrypoints (Auto-Capture, Layer 0)."""


@hook.command(name="session-start")
def session_start() -> None:
    """Read a SessionStart payload from stdin and emit session_started.

    Always exits 0: a hook must never break the host session.
    """
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    if isinstance(payload, dict):
        handle_session_start(payload)


if __name__ == "__main__":  # pragma: no cover
    main()
