#!/usr/bin/env python3

import shutil
from pathlib import Path

from gather_info import RepositorySetup


RESOURCES_DIRECTORY = Path(__file__).resolve().parents[2] / "resources"
LICENSES = {
	"agpl": RESOURCES_DIRECTORY / "LICENSE.agpl",
	"apache": RESOURCES_DIRECTORY / "LICENSE.apache",
	"closed": RESOURCES_DIRECTORY / "LICENSE.closed",
}


def setup_license(setup: RepositorySetup) -> None:
	source = LICENSES[setup.license_name]
	if not source.is_file():
		raise FileNotFoundError(f"License resource does not exist: {source}")

	shutil.copy2(source, setup.repository / "LICENSE")
	print(f"Set {setup.license_name} license for {setup.repository}.")