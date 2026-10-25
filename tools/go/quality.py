#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Optional


CHECKS: tuple[tuple[str, list[str]], ...] = (
	("race detector", ["go", "test", "-race", "./..."]),
	("coverage", ["go", "test", "-cover", "./..."]),
	("staticcheck", ["staticcheck", "./..."]),
	("golangci-lint", ["golangci-lint", "run", "--disable", "errcheck"]),
	("govulncheck", ["govulncheck", "./..."]),
)


def executable(name: str) -> Optional[str]:
	candidates = [shutil.which(name)]
	gobin = os.environ.get("GOBIN")
	if gobin:
		candidates.append(str(Path(gobin) / name))
	candidates.extend(
		(
			str(Path.home() / "go" / "bin" / name),
			f"/opt/homebrew/bin/{name}",
			f"/usr/local/go/bin/{name}",
			f"/usr/local/bin/{name}",
		)
	)
	for candidate in candidates:
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

	commands: list[tuple[str, list[str]]] = []
	missing: list[str] = []
	for check, arguments in CHECKS:
		command_executable = executable(arguments[0])
		if command_executable is None:
			missing.append(arguments[0])
		else:
			commands.append((check, [command_executable, *arguments[1:]]))

	if missing:
		print(
			"Could not find required executables: "
			f"{', '.join(sorted(set(missing)))}. "
			"Add them to PATH or install them before running quality.",
			file=sys.stderr,
		)
		return 2

	tool_paths = list(dict.fromkeys(str(Path(command[0]).parent) for _, command in commands))
	environment = os.environ.copy()
	environment["PATH"] = os.pathsep.join((*tool_paths, environment.get("PATH", "")))

	failures: list[tuple[str, list[str]]] = []
	for check, command in commands:
		print(f"\n=====> [{root}] Running {check}...\n")
		try:
			subprocess.run(command, cwd=root, check=True, env=environment)
		except (OSError, subprocess.CalledProcessError):
			failures.append((check, command))

	if failures:
		print("Quality check failures:", file=sys.stderr)
		for check, command in failures:
			print(f"- {check} ({' '.join(command)})", file=sys.stderr)
		return 1

	print(f"=====> [{root}] All quality checks passed!")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())