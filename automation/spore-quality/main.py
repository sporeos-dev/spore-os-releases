#!/usr/bin/env python3

import argparse
from pathlib import Path
import subprocess
import sys

PROJECTS: tuple[tuple[str, str], ...] = (
	("spore-client-libs/parser", "c"),
	("spore-os/spored", "go"),
	("spore-client-libs/spore_c", "c"),
	("spore-client-libs/spore_go", "go"),
	("spore-core-nodes/spore", "go"),
	("spore-core-nodes/spore-log", "go"),
	("spore-core-nodes/spore-shell", "go"),
	("spore-core-nodes/spore-witness", "go"),
	("spore-hyphae/hyphae", "go"),
	("spore-dialog/spore-dialog", "go"),
	("spore-smoke/smoke", "go"),
	("spore-smoke/report", "go"),
	("spore-store/store", "go"),
	("spore-git/git", "go"),
)


def run_go_checks(project_root: Path) -> list[str]:
	failures: list[str] = []
	for check, command in (
		("race detector", ["go", "test", "-race", "./..."]),
		("coverage", ["go", "test", "-cover", "./..."]),
		("staticcheck", ["staticcheck", "./..."]),
		("golangci-lint", ["golangci-lint", "run", "--disable", "errcheck"]),
		("govulncheck", ["govulncheck", "./..."]),
	):
		print(f"==> Running {check}...")
		try:
			subprocess.run(command, cwd=project_root, check=True)
		except (OSError, subprocess.CalledProcessError):
			failures.append(check)

	if not failures:
		print("==> All quality checks passed.")

	return failures


def run_c_checks(project_root: Path) -> list[str]:
	print("==> Running make analyze...")
	try:
		subprocess.run(["make", "analyze"], cwd=project_root, check=True)
	except (OSError, subprocess.CalledProcessError):
		return ["analyze"]

	return []


def main() -> int:
	parser = argparse.ArgumentParser()
	project_paths = tuple(project_path for project_path, _ in PROJECTS)
	parser.add_argument("project", nargs="?", choices=project_paths)
	arguments = parser.parse_args()
	projects = (
		((arguments.project, next(language for project_path, language in PROJECTS if project_path == arguments.project)),)
		if arguments.project
		else PROJECTS
	)
	development_directory = Path(__file__).resolve().parents[3]
	failures: list[tuple[str, str]] = []

	for project_path, language in projects:
		project_root = development_directory / project_path
		print(f"Checking {project_path} ({language})")
		if language == "go":
			failures.extend((project_path, check) for check in run_go_checks(project_root))
		elif language == "c":
			failures.extend((project_path, check) for check in run_c_checks(project_root))

	if failures:
		print("Quality check failures:", file=sys.stderr)
		for project_path, check in failures:
			print(f"- {project_path}: {check}", file=sys.stderr)
		return 1

	return 0


if __name__ == "__main__":
	raise SystemExit(main())