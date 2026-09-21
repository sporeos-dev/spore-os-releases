#!/usr/bin/env python3

import os
from dataclasses import dataclass
from pathlib import Path


LICENSE_NAMES = ("agpl", "apache", "closed")


@dataclass(frozen=True)
class RepositorySetup:
	repository: Path
	license_name: str


def gather_info() -> RepositorySetup:
	development_directory = _development_directory()
	repository_name = _repository_name()
	license_name = _license_name()
	repository = development_directory / repository_name

	if not repository.is_dir():
		raise FileNotFoundError(f"Repository does not exist: {repository}")

	return RepositorySetup(repository=repository, license_name=license_name)


def _development_directory() -> Path:
	dev_directory = os.environ.get("DEV")
	if not dev_directory:
		raise EnvironmentError("DEV must point to the directory containing the Spore OS repositories.")
	return Path(dev_directory).expanduser().resolve()


def _repository_name() -> str:
	repository_name = input("Repository name: ").strip()
	if not repository_name or Path(repository_name).name != repository_name:
		raise ValueError("Repository name must be a single directory name.")
	return repository_name


def _license_name() -> str:
	while True:
		license_name = input("License (agpl, apache, closed): ").strip().lower()
		if license_name in LICENSE_NAMES:
			return license_name
		print("License must be one of: agpl, apache, closed.")