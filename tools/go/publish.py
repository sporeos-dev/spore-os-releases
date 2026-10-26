#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from zipfile import BadZipFile, ZipFile


FOUNDRY_REPOSITORY = "sporeos-dev/foundry-releases"


def project_root() -> Path:
	value = os.environ.get("cwd")
	if not value:
		raise ValueError("The cwd environment variable must be set.")

	root = Path(value).expanduser().resolve()
	if not root.is_dir():
		raise ValueError(f"The cwd path is not a directory: {root}")

	return root


def required_file(name: str, root: Path) -> Path:
	value = os.environ.get(name)
	if not value:
		raise ValueError(f"The {name} environment variable must be set.")

	path = Path(value).expanduser()
	if not path.is_absolute():
		path = root / path
	path = path.resolve()
	if not path.is_file():
		raise ValueError(f"The {name} path is not a file: {path}")

	return path


def file_checksum(path: Path) -> str:
	digest = hashlib.sha256()
	with path.open("rb") as file:
		for chunk in iter(lambda: file.read(1024 * 1024), b""):
			digest.update(chunk)
	return f"sha256:{digest.hexdigest()}"


def platform_name() -> str:
	names = {
		"Darwin": "macos",
		"Linux": "linux",
		"Windows": "windows",
	}
	try:
		return names[platform.system()]
	except KeyError as error:
		raise ValueError(f"Unsupported operating system: {platform.system()}") from error


def architecture_name() -> str:
	names = {
		"aarch64": "arm64",
		"amd64": "x64",
		"arm64": "arm64",
		"x86_64": "x64",
	}
	machine = platform.machine().lower()
	try:
		return names[machine]
	except KeyError as error:
		raise ValueError(f"Unsupported architecture: {machine}") from error


def manifest_metadata(path: Path) -> dict[str, str]:
	metadata: dict[str, str] = {}
	for line in path.read_text(encoding="utf-8").splitlines():
		if line.startswith(("id:", "version:", "trust:")):
			key, _, value = line.partition(":")
			metadata[key] = value.strip()

	missing = [key for key in ("id", "version", "trust") if not metadata.get(key)]
	if missing:
		raise ValueError(
			f"The manifest is missing required fields: {', '.join(missing)}"
		)
	return metadata


def catalog_value(path: Path, key: str) -> str:
	prefix = f"{key}:"
	values: list[str] = []
	for line in path.read_text(encoding="utf-8").splitlines():
		if line.startswith(prefix):
			value = line.removeprefix(prefix).strip()
			if value:
				values.append(value)
	if len(values) > 1:
		raise ValueError(f"The catalog has multiple {key} values: {path}")
	if values:
		return values[0]
	raise ValueError(f"The catalog has no {key} value: {path}")


def foundry_root() -> Path:
	dev_directory = os.environ.get("DEV")
	if dev_directory:
		return Path(dev_directory).expanduser() / "foundry-releases"

	return Path(__file__).resolve().parents[2].parent / "foundry-releases"


def required_release_notes(root: Path) -> Path:
	path = root / "release-notes.md"
	if not path.is_file():
		raise ValueError(f"The release notes path is not a file: {path}")
	return path


def required_release_notes_template() -> Path:
	path = foundry_root() / "release-notes-template.md"
	if not path.is_file():
		raise ValueError(f"The release notes template path is not a file: {path}")
	if "{{ release_notes }}" not in path.read_text(encoding="utf-8"):
		raise ValueError(
			f"The release notes template has no {{ release_notes }} placeholder: {path}"
		)
	return path


def release_product(root: Path, catalog: Path) -> str:
	source_catalog = root / "catalog.yaml"
	if not source_catalog.is_file():
		raise ValueError(f"The source catalog path is not a file: {source_catalog}")

	try:
		source_product = catalog_value(source_catalog, "product")
	except ValueError as error:
		raise ValueError(
			"The source catalog must declare the Foundry product slug as "
			f"`product: <slug>`: {source_catalog}"
		) from error

	try:
		release_product_value = catalog_value(catalog, "product")
	except ValueError as error:
		raise ValueError(
			"The generated release catalog is missing `product`. "
			f"The source catalog declares `product: {source_product}`; rerun release "
			"to regenerate dist/catalog.yaml before publishing."
		) from error

	if release_product_value != source_product:
		raise ValueError(
			"The generated release catalog product does not match the source catalog: "
			f"`{release_product_value}` != `{source_product}`. Rerun release before "
			"publishing."
		)
	return release_product_value


def store_catalog_path() -> Path:
	dev_directory = os.environ.get("DEV")
	if dev_directory:
		return Path(dev_directory).expanduser() / "spore-store" / "store" / "catalog.yaml"

	return Path(__file__).resolve().parents[2].parent / "spore-store" / "store" / "catalog.yaml"


def run_git(root: Path, *arguments: str) -> str:
	try:
		result = subprocess.run(
			["git", *arguments],
			cwd=root,
			check=True,
			capture_output=True,
			text=True,
		)
	except subprocess.CalledProcessError as error:
		message = error.stderr.strip() or error.stdout.strip() or str(error)
		raise RuntimeError(f"git {' '.join(arguments)} failed: {message}") from error
	return result.stdout.strip()


def release_tag(version: str) -> str:
	return f"v{version}-{platform_name()}-{architecture_name()}"


def foundry_release_line(version: str) -> str:
	match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.[0-9]+", version)
	if not match:
		raise ValueError(f"The manifest version is not a.b.c: {version}")
	return f"{match.group(1)}.{match.group(2)}.x"


def foundry_release_tag(product: str, version: str) -> str:
	match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.[0-9]+", version)
	if not match:
		raise ValueError(f"The manifest version is not a.b.c: {version}")
	return f"{product}-v{match.group(1)}.{match.group(2)}"


def verify_tag(root: Path, tag: str) -> None:
	repository = Path(run_git(root, "rev-parse", "--show-toplevel")).resolve()
	tag_commit = run_git(repository, "rev-parse", f"{tag}^{{commit}}")
	head_commit = run_git(repository, "rev-parse", "HEAD")
	if tag_commit != head_commit:
		raise ValueError(f"The release tag does not point to HEAD: {tag}")
	run_git(repository, "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{tag}")


def verify_archive(
	archive: Path,
	manifest: Path,
	executable: Path,
	catalog: Path,
) -> None:
	expected = {manifest.name, executable.name, "catalog.yaml"}
	try:
		with ZipFile(archive) as zip_file:
			names = set(zip_file.namelist())
			missing = expected - names
			if missing:
				raise ValueError(
					f"The release archive is missing: {', '.join(sorted(missing))}"
				)
			if zip_file.read("catalog.yaml") != catalog.read_bytes():
				raise ValueError("The release archive catalog does not match dist/catalog.yaml.")
	except BadZipFile as error:
		raise ValueError(f"The release archive is invalid: {archive}") from error


def verify_store_catalog(store_catalog: Path, release_catalog: Path) -> None:
	if not store_catalog.is_file():
		raise ValueError(f"The store catalog path is not a file: {store_catalog}")

	release_lines = [
		line
		for line in release_catalog.read_text(encoding="utf-8").splitlines()
		if line.strip()
	]
	if not release_lines:
		raise ValueError(f"The release catalog is empty: {release_catalog}")
	entry = "\n".join(
		[
			f"  - {release_lines[0]}",
			*(f"    {line}" if line else line for line in release_lines[1:]),
		]
	)
	if entry not in store_catalog.read_text(encoding="utf-8"):
		raise ValueError(
			f"The store catalog does not contain the generated release entry: {store_catalog}"
		)


def store_manifest_path(store_catalog: Path, manifest: Path) -> Path:
	return store_catalog.parent / "manifests" / manifest.name


def verify_store_manifest(store_manifest: Path, manifest: Path) -> None:
	if not store_manifest.is_file():
		raise ValueError(f"The store manifest path is not a file: {store_manifest}")
	if file_checksum(store_manifest) != file_checksum(manifest):
		raise ValueError(
			f"The store manifest does not match the release manifest: {store_manifest}"
		)


def verify_store_worktree(store_catalog: Path, store_manifest: Path) -> None:
	repository = Path(run_git(store_catalog.parent, "rev-parse", "--show-toplevel")).resolve()
	try:
		catalog_path = store_catalog.resolve().relative_to(repository).as_posix()
		manifest_path = store_manifest.resolve().relative_to(repository).as_posix()
	except ValueError as error:
		raise ValueError(
			"The store catalog and manifest must be inside its Git repository."
		) from error

	staged = run_git(repository, "diff", "--cached", "--name-only")
	if staged:
		raise ValueError(
			"Store repository has staged changes; commit or unstage them before "
			f"publishing:\n{staged}"
		)

	untracked = set(
		run_git(repository, "ls-files", "--others", "--exclude-standard").splitlines()
	)
	unexpected_untracked = untracked - {manifest_path}
	if unexpected_untracked:
		files = "\n".join(sorted(unexpected_untracked))
		raise ValueError(
			"Store repository has untracked files; commit, stash, or remove them "
			f"before publishing:\n{files}"
		)

	changed_paths = set(run_git(repository, "diff", "--name-only").splitlines())
	expected_changed_paths = {catalog_path, manifest_path}
	if (
		catalog_path not in changed_paths
		or not changed_paths <= expected_changed_paths
	):
		changes = "\n".join(sorted(changed_paths)) or "none"
		raise ValueError(
			"Store repository must have an unstaged store/catalog.yaml change and "
			"may only also change the copied manifest before publishing; found:\n"
			f"{changes}"
		)


def release_platforms(catalog: Path) -> list[str]:
	platforms: list[str] = []
	in_releases = False
	current_opsys: str | None = None
	for line in catalog.read_text(encoding="utf-8").splitlines():
		if line == "releases:":
			in_releases = True
			continue
		if in_releases:
			opsys_match = re.fullmatch(r"  - opsys: (macos|linux|windows)", line)
			if opsys_match:
				current_opsys = opsys_match.group(1)
				continue
			arch_match = re.fullmatch(r"    arch: (arm64|x64)", line)
			if arch_match and current_opsys:
				platforms.append(f"{current_opsys}-{arch_match.group(1)}")
	if not platforms:
		raise ValueError(f"The release catalog has no platforms: {catalog}")
	return platforms


def render_release_notes(
	template: Path,
	update: Path,
	catalog: Path,
) -> str:
	values = {
		"name": catalog_value(catalog, "name"),
		"release_line": foundry_release_line(catalog_value(catalog, "version")),
		"state": catalog_value(catalog, "state"),
		"description": catalog_value(catalog, "description"),
		"platforms": "\n".join(f"- `{name}`" for name in release_platforms(catalog)),
		"release_notes": update.read_text(encoding="utf-8").strip(),
	}
	content = template.read_text(encoding="utf-8")
	for key, value in values.items():
		content = content.replace(f"{{{{ {key} }}}}", value)
	if "{{" in content:
		raise ValueError(f"The release notes template has an unknown placeholder: {template}")
	return content


def run_gh(*arguments: str) -> str:
	gh = github_cli()
	try:
		result = subprocess.run(
			[gh, *arguments],
			check=True,
			capture_output=True,
			text=True,
		)
	except subprocess.CalledProcessError as error:
		message = error.stderr.strip() or error.stdout.strip() or str(error)
		raise RuntimeError(f"gh {' '.join(arguments)} failed: {message}") from error
	return result.stdout.strip()


def github_cli() -> str:
	windows_install = (
		Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
		/ "GitHub CLI"
		/ "gh.exe"
	)
	candidates = (
		shutil.which("gh"),
		str(windows_install),
		"/opt/homebrew/bin/gh",
		"/usr/local/bin/gh",
	)
	for candidate in candidates:
		if candidate and Path(candidate).is_file():
			return candidate
	raise ValueError(
		"Could not find the GitHub CLI. Install it with `brew install gh` or add "
		"the directory containing `gh` to PATH."
	)


def verify_gh_authentication() -> None:
	run_gh("auth", "status")


def foundry_release_exists(tag: str) -> bool:
	result = subprocess.run(
		[
			github_cli(),
			"release",
			"view",
			tag,
			"--repo",
			FOUNDRY_REPOSITORY,
		],
		capture_output=True,
		text=True,
	)
	if result.returncode == 0:
		return True
	if result.returncode == 1:
		return False
	message = result.stderr.strip() or result.stdout.strip() or str(result)
	raise RuntimeError(f"Could not check Foundry release {tag}: {message}")


def publish_foundry_release(
	tag: str,
	title: str,
	state: str,
	notes: str,
	archive: Path,
	manifest: Path,
) -> None:
	if state not in ("alpha", "beta", "stable"):
		raise ValueError(f"Unsupported release state: {state}")

	print(
		"Authenticating with GitHub CLI to publish the asset to "
		f"{FOUNDRY_REPOSITORY}."
	)
	if foundry_release_exists(tag):
		arguments = [
			"release",
			"edit",
			tag,
			"--repo",
			FOUNDRY_REPOSITORY,
			"--title",
			title,
			"--notes",
			notes,
		]
		if state in ("alpha", "beta"):
			arguments.append("--prerelease")
		run_gh(*arguments)
		run_gh(
			"release",
			"upload",
			tag,
			str(archive),
			str(manifest),
			"--repo",
			FOUNDRY_REPOSITORY,
			"--clobber",
		)
		return

	arguments = [
		"release",
		"create",
		tag,
		str(archive),
		str(manifest),
		"--repo",
		FOUNDRY_REPOSITORY,
		"--title",
		title,
		"--notes",
		notes,
	]
	if state in ("alpha", "beta"):
		arguments.append("--prerelease")
	run_gh(*arguments)


def commit_and_push_store_release(
	store_catalog: Path,
	store_manifest: Path,
	node_id: str,
	version: str,
) -> None:
	verify_store_worktree(store_catalog, store_manifest)
	repository = Path(run_git(store_catalog.parent, "rev-parse", "--show-toplevel")).resolve()
	try:
		catalog_path = store_catalog.resolve().relative_to(repository)
		manifest_path = store_manifest.resolve().relative_to(repository)
	except ValueError as error:
		raise ValueError(
			"The store catalog and manifest must be inside its Git repository."
		) from error

	branch = run_git(repository, "branch", "--show-current")
	if not branch:
		raise ValueError("Cannot publish the store catalog from a detached HEAD.")

	platform = f"{platform_name()}-{architecture_name()}"
	run_git(repository, "add", "--", str(catalog_path), str(manifest_path))
	run_git(
		repository,
		"commit",
		"-m",
		f"Publish {node_id} v{version} for {platform}",
		"-m",
		"Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>",
	)
	print(
		"Authenticating with GitHub to push the published catalog "
		"to the spore-store repository."
	)
	run_git(repository, "push", "origin", branch)


def main() -> int:
	try:
		root = project_root()
		manifest = required_file("manifest", root)
		executable = required_file("executable", root)
		output_directory = root.parent / "dist"
		catalog = output_directory / "catalog.yaml"
		if not catalog.is_file():
			raise ValueError(f"The release catalog path is not a file: {catalog}")

		metadata = manifest_metadata(manifest)
		release_manifest = output_directory / manifest.name
		if not release_manifest.is_file():
			raise ValueError(
				f"The release manifest path is not a file: {release_manifest}"
			)
		release_metadata = manifest_metadata(release_manifest)
		if (
			release_metadata["id"] != metadata["id"]
			or release_metadata["version"] != metadata["version"]
		):
			raise ValueError(
				"The release manifest ID or version does not match the source manifest."
			)
		if release_metadata["trust"].strip("'\"") != "standard":
			raise ValueError(
				"The release manifest trust must be standard: "
				f"{release_manifest}"
			)
		if catalog_value(catalog, "id") != release_metadata["id"]:
			raise ValueError("The release catalog ID does not match the manifest.")
		if catalog_value(catalog, "version") != release_metadata["version"]:
			raise ValueError("The release catalog version does not match the manifest.")
		if catalog_value(catalog, "manifest") != manifest.name:
			raise ValueError("The release catalog manifest does not match the manifest file.")
		if catalog_value(catalog, "checksum") != file_checksum(release_manifest):
			raise ValueError("The release catalog checksum does not match the manifest.")
		product = release_product(root, catalog)
		release_notes = required_release_notes(root)
		release_notes_template = required_release_notes_template()

		tag = release_tag(metadata["version"])
		archive = output_directory / (
			f"{executable.stem}-{platform_name()}-{architecture_name()}.zip"
		)
		if not archive.is_file():
			raise ValueError(f"The release archive path is not a file: {archive}")

		verify_tag(root, tag)
		verify_archive(archive, release_manifest, executable, catalog)
		store_catalog = store_catalog_path()
		store_manifest = store_manifest_path(store_catalog, release_manifest)
		verify_store_worktree(store_catalog, store_manifest)
		verify_store_catalog(store_catalog, catalog)
		verify_store_manifest(store_manifest, release_manifest)
		print(
			"Checking GitHub CLI authentication before publishing the "
			f"asset to {FOUNDRY_REPOSITORY}."
		)
		verify_gh_authentication()

		foundry_tag = foundry_release_tag(product, metadata["version"])
		foundry_title = (
			f"{catalog_value(catalog, 'name')} "
			f"{foundry_release_line(metadata['version'])}"
		)
		publish_foundry_release(
			foundry_tag,
			foundry_title,
			catalog_value(catalog, "state"),
			render_release_notes(release_notes_template, release_notes, catalog),
			archive,
			release_manifest,
		)
		commit_and_push_store_release(
			store_catalog,
			store_manifest,
			metadata["id"],
			metadata["version"],
		)
	except (OSError, RuntimeError, ValueError, UnicodeError) as error:
		print(f"Publish validation failed: {error}", file=sys.stderr)
		return 1

	print(
		f"Published {archive.name} and {release_manifest.name} "
		f"to Foundry release {foundry_tag}."
	)
	print("Published the store catalog update.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())