#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Optional


CHECKS: tuple[tuple[str, str, list[str]], ...] = (
	("clean", "Cleaning build and test cache...", ["go", "clean", "-cache", "-testcache"]),
	("build", "Building...", ["go", "build", "./..."]),
	("vet", "Vetting...", ["go", "vet", "./..."]),
	("test", "Testing...", ["go", "test", "./..."]),
)


def go_executable() -> str | None:
	for candidate in (
		shutil.which("go"),
		"/opt/homebrew/bin/go",
		"/usr/local/go/bin/go",
		"/usr/local/bin/go",
	):
		if candidate and Path(candidate).is_file():
			return candidate

	return None


def project_root() -> Optional[Path]:
	value = os.environ.get("cwd")
	if not value:
		print("The cwd environment variable must be set.", file=sys.stderr)
		return None

	root = Path(value).expanduser()
	if not root.is_dir():
		print(f"The cwd path is not a directory: {root}", file=sys.stderr)
		return None

	return root


def main() -> int:
	root = project_root()
	if root is None:
		return 2

	go = go_executable()
	if go is None:
		print(
			"Could not find the Go executable. Add Go to PATH or install it before running quick.",
			file=sys.stderr,
		)
		return 2

	failures: list[tuple[str, list[str]]] = []
	for check, message, arguments in CHECKS:
		command = [go, *arguments[1:]]
		print(f"\n=====> [{root}] {message}\n")
		try:
			subprocess.run(command, cwd=root, check=True)
		except (OSError, subprocess.CalledProcessError):
			failures.append((check, command))

	if failures:
		print("Quick check failures:", file=sys.stderr)
		for check, command in failures:
			print(f"- {check} ({' '.join(command)})", file=sys.stderr)
		return 1

	print(f"=====> [{root}] All checks passed!")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())