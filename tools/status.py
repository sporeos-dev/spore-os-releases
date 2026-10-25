#!/usr/bin/env python3
"""Show a compact summary of changes in sibling Git repositories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from repositories import REPOSITORY_ROOT, SIBLING_ROOT, git, location, repositories, tracking_status


@dataclass(frozen=True)
class ChangeSummary:
    staged: int
    unstaged: int
    untracked: int

    @property
    def total(self) -> int:
        return self.staged + self.unstaged + self.untracked


def repository_changes(repository: Path) -> ChangeSummary:
    result = git(repository, "status", "--porcelain=v1", "--untracked-files=normal")
    if result.returncode:
        message = result.stderr.strip() or "git status failed"
        raise RuntimeError(f"{repository}: {message}")

    staged = 0
    unstaged = 0
    untracked = 0
    for line in result.stdout.splitlines():
        if line.startswith("??"):
            untracked += 1
            continue
        if line[0] != " ":
            staged += 1
        if line[1] != " ":
            unstaged += 1

    return ChangeSummary(staged, unstaged, untracked)

def main() -> int:
    repository_paths = repositories()
    if not repository_paths:
        print(f"No sibling Git repositories found under {SIBLING_ROOT}.")
        return 0

    changed_repositories: list[tuple[Path, ChangeSummary]] = []
    for repository in repository_paths:
        try:
            summary = repository_changes(repository)
        except (OSError, RuntimeError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        if summary.total:
            changed_repositories.append((repository, summary))

    if not changed_repositories:
        print("No changes found in sibling repositories.")
        return 0

    print(
        "Repository (relative to spore-os-releases)   staged  unstaged  "
        "untracked  total  branch  upstream  ahead  behind"
    )
    for repository, summary in changed_repositories:
        try:
            tracking = tracking_status(repository)
        except RuntimeError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        branch = tracking.branch if tracking else " detached"
        upstream = tracking.upstream if tracking else "—"
        ahead = tracking.ahead if tracking else "—"
        behind = tracking.behind if tracking else "—"
        print(
            f"{location(repository):<42} {summary.staged:>7} {summary.unstaged:>9}"
            f" {summary.untracked:>10} {summary.total:>6}"
            f"  {branch:<8} {upstream:<14} {ahead:>5} {behind:>6}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
