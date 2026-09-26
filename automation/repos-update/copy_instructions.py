#!/usr/bin/env python3

import os
import shutil
import sys
from pathlib import Path


RELEASES_REPOSITORY = "spore-os-releases"
INSTRUCTION_PATHS = (
	Path(".github/instructions/repomap.instructions.md"),
	Path(".github/instructions/testing.instructions.md"),
)
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
	canonical_repository = development_root / RELEASES_REPOSITORY
	for instruction_path in INSTRUCTION_PATHS:
		source = canonical_repository / instruction_path
		if not source.is_file():
			sys.exit(f"Canonical instruction does not exist: {source}")

	for repository in REPOSITORIES:
		print(f"\nUpdating instructions for {repository}\n")
		for instruction_path in INSTRUCTION_PATHS:
			source = canonical_repository / instruction_path
			destination = development_root / repository / instruction_path
			destination.parent.mkdir(parents=True, exist_ok=True)
			shutil.copy2(source, destination)
			print(f"Copied instruction to {destination}")


if __name__ == "__main__":
	main()