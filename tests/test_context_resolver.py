"""Tests for the context_resolver deep module.

context_resolver answers one question for every Auto-Capture event: which
Issue Attempt does this belong to? It infers the repo (from the git remote) and
the issue number (from branch naming conventions and commit/PR references like
``fixes #14``). When neither can be determined the context is flagged
*unattributed* — never dropped (PRD story 22).

The public surface is one function, :func:`resolve`, returning an immutable
:class:`ResolvedContext`. The inference table for branch names and commit-message
references is exercised exhaustively below.
"""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path

import pytest

from sdlc_eval.context_resolver import (
    ResolvedContext,
    issue_from_branch,
    issue_from_text,
    resolve,
)

# --- branch-name inference table -----------------------------------------

# (branch, expected issue or None) — exhaustive across the documented
# conventions plus convention-free and adversarial inputs.
BRANCH_CASES = [
    # issue-14-* convention
    ("issue-14-add-resolver", 14),
    ("issue-7", 7),
    # 14-* convention
    ("14-add-resolver", 14),
    ("3-fix-bug", 3),
    # feature/14-* convention (and other prefixes)
    ("feature/14-add-resolver", 14),
    ("feat/22-thing", 22),
    ("fix/108-regression", 108),
    ("bugfix/9-crash", 9),
    # issue/ prefix variant
    ("issue/14-add-resolver", 14),
    # multi-digit
    ("issue-12345-big", 12345),
    # convention-free → no issue
    ("main", None),
    ("develop", None),
    ("release", None),
    ("my-cool-branch", None),
    ("", None),
    # a leading number that is not an issue ref (no separator after digits
    # at start counts, but a word like "v2" should not be read as issue 2)
    ("v2-something", None),
    ("2024-archive", 2024),  # bare leading number IS the convention
]


@pytest.mark.parametrize("branch, expected", BRANCH_CASES)
def test_issue_from_branch(branch: str, expected: int | None) -> None:
    assert issue_from_branch(branch) == expected


# --- commit-message / PR reference inference table ------------------------

TEXT_CASES = [
    ("fixes #14", 14),
    ("Fixes #14", 14),
    ("FIXES #14", 14),
    ("closes #14", 14),
    ("Closes #22", 22),
    ("close #5", 5),
    ("fix #5", 5),
    ("resolve #5", 5),
    ("resolves #5", 5),
    ("fixed #5", 5),
    ("closed #5", 5),
    ("resolved #5", 5),
    ("a bare #14 reference", 14),
    ("multiline\nbody\ncloses #99", 99),
    ("relates to #3 but really closes #14", 3),  # first ref wins
    ("no reference here", None),
    ("", None),
    ("issue number 14 with no hash", None),
    ("email me at user#14 not a ref", 14),  # tolerant: #<n> is a ref
]


@pytest.mark.parametrize("text, expected", TEXT_CASES)
def test_issue_from_text(text: str, expected: int | None) -> None:
    assert issue_from_text(text) == expected


# --- ResolvedContext value object ----------------------------------------


def test_resolved_context_is_immutable() -> None:
    ctx = ResolvedContext(repo="o/r", issue=14, attributed=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.issue = 7  # type: ignore[misc]


def test_attributed_context_has_repo_and_issue() -> None:
    ctx = ResolvedContext(repo="o/r", issue=14, attributed=True)
    assert ctx.repo == "o/r"
    assert ctx.issue == 14
    assert ctx.attributed is True


def test_unattributed_marker_is_explicit() -> None:
    ctx = ResolvedContext.unattributed(repo="o/r")
    assert ctx.attributed is False
    assert ctx.issue is None
    assert ctx.repo == "o/r"


def test_unattributed_marker_without_repo() -> None:
    ctx = ResolvedContext.unattributed()
    assert ctx.attributed is False
    assert ctx.issue is None
    assert ctx.repo is None


# --- git-backed resolution: fixtures --------------------------------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(path: Path, remote: str | None, branch: str | None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    if remote is not None:
        _git(path, "remote", "add", "origin", remote)
    if branch is not None:
        _git(path, "checkout", "-q", "-b", branch)
        # need a commit so the branch is real / HEAD is not unborn
        (path / "f").write_text("x")
        _git(path, "add", "f")
        _git(path, "commit", "-q", "-m", "init")
    return path


def test_resolve_reads_repo_from_https_remote(tmp_path: Path) -> None:
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/chijunzheng/owners-manual.git",
        branch="issue-14-thing",
    )
    ctx = resolve(str(repo), {})
    assert ctx.repo == "chijunzheng/owners-manual"
    assert ctx.issue == 14
    assert ctx.attributed is True


def test_resolve_reads_repo_from_ssh_remote(tmp_path: Path) -> None:
    repo = _init_repo(
        tmp_path / "wt",
        remote="git@github.com:chijunzheng/owners-manual.git",
        branch="14-thing",
    )
    ctx = resolve(str(repo), {})
    assert ctx.repo == "chijunzheng/owners-manual"
    assert ctx.issue == 14


def test_resolve_strips_dot_git_suffix(tmp_path: Path) -> None:
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/o/n.git",
        branch="feature/9-x",
    )
    assert resolve(str(repo), {}).repo == "o/n"


def test_resolve_handles_remote_without_dot_git(tmp_path: Path) -> None:
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/o/n",
        branch="9-x",
    )
    assert resolve(str(repo), {}).repo == "o/n"


# --- git-backed resolution: unattributed paths ----------------------------


def test_resolve_non_git_directory_is_unattributed(tmp_path: Path) -> None:
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    ctx = resolve(str(plain), {})
    assert ctx.attributed is False
    assert ctx.issue is None


def test_resolve_nonexistent_directory_is_unattributed(tmp_path: Path) -> None:
    ctx = resolve(str(tmp_path / "missing"), {})
    assert ctx.attributed is False
    assert ctx.issue is None


def test_resolve_convention_free_branch_is_unattributed(tmp_path: Path) -> None:
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/o/n.git",
        branch="main",
    )
    ctx = resolve(str(repo), {})
    assert ctx.repo == "o/n"  # repo still known
    assert ctx.issue is None
    assert ctx.attributed is False  # no issue → unattributed


def test_resolve_detached_head_is_unattributed(tmp_path: Path) -> None:
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/o/n.git",
        branch="issue-14-thing",
    )
    # Detach HEAD onto the current commit.
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _git(repo, "checkout", "-q", head)
    ctx = resolve(str(repo), {})
    assert ctx.repo == "o/n"
    assert ctx.issue is None
    assert ctx.attributed is False


def test_resolve_repo_without_remote_falls_back_to_basename(tmp_path: Path) -> None:
    """No remote → derive repo label from the worktree basename, still resolve issue."""
    repo = _init_repo(
        (tmp_path / "owners-manual"),
        remote=None,
        branch="issue-14-thing",
    )
    ctx = resolve(str(repo), {})
    assert ctx.repo == "owners-manual"
    assert ctx.issue == 14
    assert ctx.attributed is True


# --- payload-driven resolution (commit/PR refs) ---------------------------


def test_resolve_uses_commit_message_ref_when_branch_silent(tmp_path: Path) -> None:
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/o/n.git",
        branch="main",  # convention-free branch
    )
    ctx = resolve(str(repo), {"commit_message": "wire it up\n\ncloses #14"})
    assert ctx.repo == "o/n"
    assert ctx.issue == 14
    assert ctx.attributed is True


def test_resolve_branch_wins_over_commit_message(tmp_path: Path) -> None:
    """Branch convention is the stronger signal than a commit-message ref."""
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/o/n.git",
        branch="issue-7-thing",
    )
    ctx = resolve(str(repo), {"commit_message": "closes #14"})
    assert ctx.issue == 7


def test_resolve_uses_payload_pr_body_ref(tmp_path: Path) -> None:
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/o/n.git",
        branch="main",
    )
    ctx = resolve(str(repo), {"pr_body": "Some work.\n\nFixes #22"})
    assert ctx.issue == 22


def test_resolve_explicit_payload_issue_wins(tmp_path: Path) -> None:
    """An explicit numeric issue in the payload is authoritative."""
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/o/n.git",
        branch="main",
    )
    ctx = resolve(str(repo), {"issue": 99})
    assert ctx.issue == 99
    assert ctx.attributed is True


def test_resolve_payload_repo_overrides_remote(tmp_path: Path) -> None:
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/o/n.git",
        branch="issue-14-x",
    )
    ctx = resolve(str(repo), {"repo": "explicit/override"})
    assert ctx.repo == "explicit/override"


# --- robustness -----------------------------------------------------------


def test_resolve_tolerates_missing_cwd() -> None:
    """A None/empty cwd must not raise; it resolves to unattributed."""
    ctx = resolve(None, {})  # type: ignore[arg-type]
    assert ctx.attributed is False


def test_resolve_tolerates_non_mapping_payload(tmp_path: Path) -> None:
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/o/n.git",
        branch="issue-14-x",
    )
    ctx = resolve(str(repo), None)  # type: ignore[arg-type]
    assert ctx.repo == "o/n"
    assert ctx.issue == 14


def test_resolve_missing_cwd_still_uses_payload_refs() -> None:
    """No cwd but a payload ref → attributed from text alone (never dropped)."""
    ctx = resolve(None, {"repo": "o/n", "commit_message": "closes #14"})  # type: ignore[arg-type]
    assert ctx.repo == "o/n"
    assert ctx.issue == 14
    assert ctx.attributed is True


def test_resolve_missing_cwd_with_explicit_string_issue() -> None:
    ctx = resolve(None, {"repo": "o/n", "issue": "22"})  # type: ignore[arg-type]
    assert ctx.issue == 22
    assert ctx.attributed is True


def test_resolve_nonexistent_cwd_uses_payload_refs() -> None:
    """A nonexistent cwd but a payload ref → attributed from text, not dropped."""
    ctx = resolve("/no/such/dir", {"repo": "o/n", "pr_body": "Fixes #7"})
    assert ctx.repo == "o/n"
    assert ctx.issue == 7
    assert ctx.attributed is True


def test_resolve_explicit_string_issue_from_git_dir(tmp_path: Path) -> None:
    repo = _init_repo(
        tmp_path / "wt",
        remote="https://github.com/o/n.git",
        branch="main",
    )
    ctx = resolve(str(repo), {"issue": "55"})
    assert ctx.issue == 55
