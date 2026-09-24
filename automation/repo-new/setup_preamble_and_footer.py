#!/usr/bin/env python3

from pathlib import Path

from gather_info import RepositorySetup


RESOURCES_DIRECTORY = Path(__file__).resolve().parents[2] / "resources"
LICENSE_TYPES = {
	"agpl": "AGPL-3.0-only",
	"apache": "Apache-2.0",
	"closed": "Proprietary",
}


def setup_preamble_and_footer(setup: RepositorySetup) -> None:
	preamble = _resource("preamble.md")
	footer = _resource("footer.md").replace("LICENSE_TYPE", LICENSE_TYPES[setup.license_name])
	readme = setup.repository / "README.md"
	contents = readme.read_text(encoding="utf-8") if readme.is_file() else ""
	updated_contents = _add_section(contents, preamble, at_start=True)
	updated_contents = _add_section(updated_contents, footer, at_start=False)

	if updated_contents != contents:
		readme.write_text(updated_contents, encoding="utf-8")
		print(f"Set up README preamble and footer for {setup.repository}.")


def _resource(name: str) -> str:
	resource = RESOURCES_DIRECTORY / name
	if not resource.is_file():
		raise FileNotFoundError(f"Resource does not exist: {resource}")
	return resource.read_text(encoding="utf-8").strip()


def _add_section(contents: str, section: str, at_start: bool) -> str:
	begin_marker = section.splitlines()[0]
	if begin_marker in contents:
		return contents

	if not contents.strip():
		return f"{section}\n"
	if at_start:
		return f"{section}\n\n{contents.rstrip()}\n"
	return f"{contents.rstrip()}\n\n{section}\n"