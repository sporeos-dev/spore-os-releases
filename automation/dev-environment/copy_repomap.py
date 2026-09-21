#!/usr/bin/env python3

import os
import shutil
import sys
from pathlib import Path


RELEASES_REPOSITORY = "spore-os-releases"
REPOMAP_PATH = Path(".github/instructions/repomap.instructions.md")
REPOSITORIES = (
	"spore-os-protocol",
	"spore-install",

	"spore-os",
	"spore-client-libs",
	"spore-core-nodes",
	"spore-hyphae",
	"spore-dialog",
	"spore-store",
	"spore-smoke",

    "spore-git",
)


def main() -> None:
	dev_directory = os.environ.get("DEV")
	if not dev_directory:
		sys.exit("DEV must point to the directory containing the Spore OS repositories.")

	development_root = Path(dev_directory).expanduser().resolve()
	source = development_root / RELEASES_REPOSITORY / REPOMAP_PATH
	if not source.is_file():
		sys.exit(f"Canonical repomap does not exist: {source}")

	for repository in REPOSITORIES:
		destination = development_root / repository / REPOMAP_PATH
		destination.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(source, destination)
		print(f"Copied repomap to {destination}")


if __name__ == "__main__":
	main()
