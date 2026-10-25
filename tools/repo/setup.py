#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


AUTOMATION_DIRECTORY = Path(__file__).resolve().parents[2] / "automation"
REPO_NEW_DIRECTORY = AUTOMATION_DIRECTORY / "repo-new"
REPOS_UPDATE_SCRIPT = AUTOMATION_DIRECTORY / "repos-update" / "main.py"
LICENSE_NAMES = ("agpl", "apache", "closed")


def repository_root() -> Path | None:
	value = os.environ.get("cwd")
	if not value:
		print("The cwd environment variable must be set.", file=sys.stderr)
		return None

	root = Path(value).expanduser().resolve()
	if not root.is_dir():
		print(f"The cwd path is not a directory: {root}", file=sys.stderr)
		return None

	return root


def license_name() -> str | None:
	value = os.environ.get("license")
	if not value:
		print(
			"The license environment variable must be set "
			"(agpl, apache, or closed).",
			file=sys.stderr,
		)
		return None

	name = value.strip().lower()
	if name not in LICENSE_NAMES:
		print(
			f"Unsupported license {value!r}; choose one of: "
			f"{', '.join(LICENSE_NAMES)}.",
			file=sys.stderr,
		)
		return None
	return name


def main() -> int:
	root = repository_root()
	if root is None:
		return 2
	license = license_name()
	if license is None:
		return 2

	for module in ("gather_info", "setup_license", "setup_preamble_and_footer"):
		if not (REPO_NEW_DIRECTORY / f"{module}.py").is_file():
			print(
				f"The repo-new automation module does not exist: "
				f"{REPO_NEW_DIRECTORY / f'{module}.py'}",
				file=sys.stderr,
			)
			return 2

	sys.path.insert(0, str(REPO_NEW_DIRECTORY))
	from gather_info import RepositorySetup
	from setup_license import setup_license
	from setup_preamble_and_footer import setup_preamble_and_footer

	setup = RepositorySetup(repository=root, license_name=license)
	print(f"\n=====> Running repo-new automation for {root}\n")
	setup_license(setup)
	setup_preamble_and_footer(setup)

	if not REPOS_UPDATE_SCRIPT.is_file():
		print(
			f"The repos-update automation script does not exist: "
			f"{REPOS_UPDATE_SCRIPT}",
			file=sys.stderr,
		)
		return 2

	print(f"\n=====> Running repos-update automation from {root.parent}\n")
	try:
		subprocess.run(
			[sys.executable, REPOS_UPDATE_SCRIPT.name],
			cwd=REPOS_UPDATE_SCRIPT.parent,
			check=True,
			env={**os.environ, "DEV": str(root.parent)},
		)
	except subprocess.CalledProcessError as error:
		return error.returncode
	except OSError as error:
		print(f"Could not run repos-update automation: {error}", file=sys.stderr)
		return 1

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
