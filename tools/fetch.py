#!/usr/bin/env python3
"""Fetch all remotes for every repository in the development directory."""

from __future__ import annotations

import sys

from repositories import git, location, repositories, tracking_status


def main() -> int:
    failures = 0
    for repository in repositories():
        print(f"{location(repository)}: fetching")
        result = git(repository, "fetch", "--all", "--prune")
        if result.returncode:
            message = result.stderr.strip() or "git fetch failed"
            print(f"{location(repository)}: error: {message}", file=sys.stderr)
            failures += 1
            continue

        try:
            tracking = tracking_status(repository)
        except RuntimeError as error:
            print(f"{error}", file=sys.stderr)
            failures += 1
            continue
        if tracking is None:
            print(f"{location(repository)}: fetched (detached HEAD)")
        elif tracking.upstream == "—":
            print(f"{location(repository)}: fetched (no upstream)")
        else:
            print(
                f"{location(repository)}: fetched "
                f"(ahead {tracking.ahead}, behind {tracking.behind})"
            )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
