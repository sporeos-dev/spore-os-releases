"""Shared repository discovery and Git helpers for the tools in this directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SIBLING_ROOT = REPOSITORY_ROOT.parent
EXCLUDED_REPOSITORIES = frozenset({"flutter"})


@dataclass(frozen=True)
class TrackingStatus:
    branch: str
    upstream: str
    ahead: int
    behind: int


def repositories() -> list[Path]:
    return sorted(
        (
            path
            for path in SIBLING_ROOT.iterdir()
            if (
                path.is_dir()
                and path.name not in EXCLUDED_REPOSITORIES
                and (path / ".git").exists()
            )
        ),
        key=lambda path: path.name.casefold(),
    )


def location(repository: Path) -> str:
    if repository == REPOSITORY_ROOT:
        return "."
    return str(Path("..") / repository.name)


def git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def is_dirty(repository: Path) -> bool:
    result = git(
        repository,
        "status",
        "--porcelain=v1",
        "--untracked-files=normal",
    )
    if result.returncode:
        message = result.stderr.strip() or "git status failed"
        raise RuntimeError(f"{repository}: {message}")
    return bool(result.stdout)


def tracking_status(repository: Path) -> TrackingStatus | None:
    branch_result = git(repository, "branch", "--show-current")
    if branch_result.returncode:
        message = branch_result.stderr.strip() or "could not read branch"
        raise RuntimeError(f"{repository}: {message}")
    branch = branch_result.stdout.strip()
    if not branch:
        return None

    upstream_result = git(
        repository,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}",
    )
    if upstream_result.returncode:
        return TrackingStatus(branch, "—", 0, 0)
    upstream = upstream_result.stdout.strip()

    count_result = git(
        repository,
        "rev-list",
        "--left-right",
        "--count",
        f"HEAD...{upstream}",
    )
    if count_result.returncode:
        message = count_result.stderr.strip() or "could not compare branches"
        raise RuntimeError(f"{repository}: {message}")
    ahead, behind = (int(value) for value in count_result.stdout.split())
    return TrackingStatus(branch, upstream, ahead, behind)
