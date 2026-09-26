#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / "resources/license.tmpl"
GO_MODULES = (
	Path("spore-os/spored"),
	Path("spore-client-libs/spore_go"),
	Path("spore-core-nodes/spore-shell"),
	Path("spore-core-nodes/spore-log"),
	Path("spore-core-nodes/spore-witness"),
	Path("spore-core-nodes/spore"),
	Path("spore-hyphae/hyphae"),
	Path("spore-dialog/spore-dialog"),
	Path("spore-store/spore-store"),
	Path("spore-smoke/spore-smoke"),
	Path("spore-smoke/spore-report"),
	Path("spore-git/spore-git"),
)

def update_attributions() -> None:
	development_directory = _development_directory()

	for module_path in GO_MODULES:
		module = development_directory / module_path
		if not (module / "go.mod").is_file():
			raise FileNotFoundError(f"Go module does not exist: {module}")

		print(f"\nUpdating attributions for {module_path}\n")
		with (module.parent / "ATTRIBUTIONS.md").open("w", encoding="utf-8") as output:
			subprocess.run(
				[
					"go-licenses",
					"report",
					"./...",
					"--template=" + str(TEMPLATE),
					"--ignore=spored",
				],
				cwd=module,
				check=True,
				stdout=output,
			)


def _development_directory() -> Path:
	dev_directory = os.environ.get("DEV")
	if not dev_directory:
		raise EnvironmentError("DEV must point to the directory containing the Spore OS repositories.")
	return Path(dev_directory).expanduser().resolve()
