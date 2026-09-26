#!/usr/bin/env python3

import os
from pathlib import Path

RESOURCES_DIRECTORY = Path(__file__).resolve().parents[2] / "resources"
REPOSITORIES = (
	("spore-os", "AGPL-3.0-only"),
	("spore-client-libs", "Apache-2.0"),
	("spore-core-nodes", "Apache-2.0"),
	("spore-hyphae", "Apache-2.0"),
	("spore-dialog", "Apache-2.0"),
	("spore-store", "Apache-2.0"),
	("spore-smoke", "Apache-2.0"),
	("spore-git", "Apache-2.0"),
)

def update_preamble_and_footer() -> None:
	preamble = (RESOURCES_DIRECTORY / "preamble.md").read_text(encoding="utf-8").rstrip()
	footer_template = (RESOURCES_DIRECTORY / "footer.md").read_text(encoding="utf-8")
	development_directory = _development_directory()

	for repository_name, license_type in REPOSITORIES:
		repository = development_directory / repository_name
		readme = repository / "README.md"
		if not readme.is_file():
			continue

		print(f"\nUpdating README preamble and footer for {repository_name}\n")
		contents = readme.read_text(encoding="utf-8")
		footer = footer_template.replace("LICENSE_TYPE", license_type).rstrip()
		updated_contents = _replace_section(contents, "PREAMBLE", preamble)
		updated_contents = _replace_section(updated_contents, "FOOTER", footer)
		if updated_contents != contents:
			readme.write_text(updated_contents.rstrip() + "\n", encoding="utf-8")

def _development_directory() -> Path:
	dev_directory = os.environ.get("DEV")
	if not dev_directory:
		raise EnvironmentError("DEV must point to the directory containing the Spore OS repositories.")
	return Path(dev_directory).expanduser().resolve()

def _replace_section(contents: str, section: str, replacement: str) -> str:
	begin = f"<!-- {section} BEGIN -->"
	end = f"<!-- {section} FIN -->"
	start = contents.find(begin)
	finish = contents.find(end)

	if start == -1 or finish == -1 or finish < start:
		return contents

	finish += len(end)
	return contents[:start] + replacement + contents[finish:]
