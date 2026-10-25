#!/usr/bin/env python3
"""Show a compact summary of changes in sibling Git repositories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SIBLING_ROOT = REPOSITORY_ROOT.parent


@dataclass(frozen=True)
class ChangeSummary:
    staged: int
    unstaged: int
    untracked: int

    @property
    def total(self) -> int:
        return self.staged + self.unstaged + self.untracked


def repository_changes(repository: Path) -> ChangeSummary:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "status",
            "--porcelain=v1",
            "--untracked-files=normal",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
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


def sibling_repositories() -> list[Path]:
    return sorted(
        (
            path
            for path in SIBLING_ROOT.iterdir()
            if (
                path.is_dir()
                and (path / ".git").exists()
            )
        ),
        key=lambda path: path.name.casefold(),
    )


def main() -> int:
    repositories = sibling_repositories()
    if not repositories:
        print(f"No sibling Git repositories found under {SIBLING_ROOT}.")
        return 0

    changed_repositories: list[tuple[Path, ChangeSummary]] = []
    for repository in repositories:
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

    print("Repository (relative to spore-os-releases)   staged  unstaged  untracked  total")
    for repository, summary in changed_repositories:
        location = (
            Path(".")
            if repository == REPOSITORY_ROOT
            else Path("..") / repository.name
        )
        print(
            f"{location!s:<42} {summary.staged:>7} {summary.unstaged:>9}"
            f" {summary.untracked:>10} {summary.total:>6}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
