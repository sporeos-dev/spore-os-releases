#!/usr/bin/env python3

import subprocess

from update_attributions import GO_MODULES, _development_directory


def finesse_go() -> None:
	development_directory = _development_directory()

	for module_path in GO_MODULES:
		module = development_directory / module_path
		if not (module / "go.mod").is_file():
			raise FileNotFoundError(f"Go module does not exist: {module}")

		subprocess.run(["go", "mod", "tidy"], cwd=module, check=True)
