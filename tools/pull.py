#!/usr/bin/env python3
"""Fast-forward clean repositories from their configured upstream branches."""

from __future__ import annotations

import sys

from repositories import git, is_dirty, location, repositories, tracking_status


def main() -> int:
    failures = 0
    for repository in repositories():
        try:
            if is_dirty(repository):
                print(f"{location(repository)}: skipped (dirty)")
                continue
            tracking = tracking_status(repository)
        except (OSError, RuntimeError) as error:
            print(f"error: {error}", file=sys.stderr)
            failures += 1
            continue

        if tracking is None:
            print(f"{location(repository)}: skipped (detached HEAD)")
            continue
        if tracking.upstream == "—":
            print(f"{location(repository)}: skipped (no upstream)")
            continue

        result = git(repository, "pull", "--ff-only")
        if result.returncode:
            message = result.stderr.strip() or "git pull failed"
            print(f"{location(repository)}: error: {message}", file=sys.stderr)
            failures += 1
        else:
            print(f"{location(repository)}: pulled")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
