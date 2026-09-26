#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path


RESOURCES_DIRECTORY = Path(__file__).resolve().parents[2] / "resources"
AGPL_HEADER = RESOURCES_DIRECTORY / "header.txt.agpl"
APACHE_HEADER = RESOURCES_DIRECTORY / "header.txt.apache"

AGPL_REPOSITORIES = ("spore-os",)
APACHE_REPOSITORIES = (
	"spore-client-libs",
	"spore-core-nodes",
	"spore-hyphae",
	"spore-dialog",
	"spore-store",
	"spore-smoke",
)

def ensure_spdx() -> None:
	try:
		development_directory = _development_directory()
		_add_headers(development_directory, AGPL_REPOSITORIES, AGPL_HEADER)
		_add_headers(development_directory, APACHE_REPOSITORIES, APACHE_HEADER)
	except (EnvironmentError, FileNotFoundError, subprocess.CalledProcessError) as error:
		print(f"SPDX update failed: {error}", file=sys.stderr)
		raise

	print("SPDX headers updated.")


def _development_directory() -> Path:
	dev_directory = os.environ.get("DEV")
	if not dev_directory:
		raise EnvironmentError("DEV must point to the directory containing the Spore OS repositories.")
	return Path(dev_directory).expanduser().resolve()


def _add_headers(development_directory: Path, repositories: tuple[str, ...], header: Path) -> None:
	if not header.is_file():
		raise FileNotFoundError(f"SPDX header does not exist: {header}")

	for repository_name in repositories:
		repository = development_directory / repository_name
		if not repository.is_dir():
			raise FileNotFoundError(f"Repository does not exist: {repository}")

		print(f"\nUpdating SPDX headers in {repository_name}\n")
		subprocess.run(
			["addlicense", "-f", str(header), "-v", "."],
			cwd=repository,
			check=True,
		)
