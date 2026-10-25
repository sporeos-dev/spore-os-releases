#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


RESOURCES_DIRECTORY = Path(__file__).resolve().parents[2] / "resources"
HEADERS = {
	"agpl": RESOURCES_DIRECTORY / "header.txt.agpl",
	"apache": RESOURCES_DIRECTORY / "header.txt.apache",
	"closed": RESOURCES_DIRECTORY / "header.txt.closed",
}


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
	if name not in HEADERS:
		print(
			f"Unsupported license {value!r}; choose one of: "
			f"{', '.join(HEADERS)}.",
			file=sys.stderr,
		)
		return None
	return name


def addlicense_executable() -> str | None:
	gobin = os.environ.get("GOBIN")
	candidates = [
		shutil.which("addlicense"),
		str(Path(gobin) / "addlicense") if gobin else None,
		str(Path.home() / "go" / "bin" / "addlicense"),
		"/opt/homebrew/bin/addlicense",
		"/usr/local/bin/addlicense",
	]
	for candidate in candidates:
		if candidate and Path(candidate).is_file():
			return candidate
	return None


def main() -> int:
	root = repository_root()
	if root is None:
		return 2

	license = license_name()
	if license is None:
		return 2

	header = HEADERS[license]
	if not header.is_file():
		print(f"Copyright header does not exist: {header}", file=sys.stderr)
		return 2

	addlicense = addlicense_executable()
	if addlicense is None:
		print(
			"Could not find addlicense. Add it to PATH or install it "
			"before running update.",
			file=sys.stderr,
		)
		return 2

	print(f"\n=====> Updating copyright headers in {root}\n")
	try:
		subprocess.run(
			[addlicense, "-f", str(header), "-v", "."],
			cwd=root,
			check=True,
			env={
				**os.environ,
				"PATH": os.pathsep.join(
					(str(Path(addlicense).parent), os.environ.get("PATH", ""))
				),
			},
		)
	except subprocess.CalledProcessError as error:
		print(f"Copyright update failed: {error}", file=sys.stderr)
		return error.returncode
	except OSError as error:
		print(f"Copyright update failed: {error}", file=sys.stderr)
		return 1

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
