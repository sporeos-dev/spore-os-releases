#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile


RELEASE_TRUST = "standard"


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
		if line.startswith(("id:", "name:", "version:", "description:", "trust:")):
			key, _, value = line.partition(":")
			metadata[key] = value.strip()

	required = ("id", "name", "version", "description", "trust")
	missing = [key for key in required if not metadata.get(key)]
	if missing:
		raise ValueError(
			f"The manifest is missing required fields: {', '.join(missing)}"
		)
	return metadata


def increment_manifest_version(path: Path) -> str:
	content = path.read_text(encoding="utf-8")
	lines = content.splitlines()
	version_pattern = re.compile(r"^version:\s*([0-9]+)\.([0-9]+)\.(x|[0-9]+)\s*$")

	for index, line in enumerate(lines):
		match = version_pattern.match(line)
		if match:
			major, minor, patch = match.groups()
			next_patch = 0 if patch == "x" else int(patch) + 1
			version = f"{major}.{minor}.{next_patch}"
			lines[index] = f"version: {version}"
			path.write_text("\n".join(lines) + "\n", encoding="utf-8")
			return version

	raise ValueError(f"The manifest has no valid top-level a.b.x version: {path}")


def replace_manifest_trust(path: Path, trust: str) -> None:
	lines = path.read_text(encoding="utf-8").splitlines()
	for index, line in enumerate(lines):
		if line.startswith("trust:"):
			lines[index] = f"trust: {trust}"
			path.write_text("\n".join(lines) + "\n", encoding="utf-8")
			return

	raise ValueError(f"The manifest has no top-level trust field: {path}")


def write_platform_catalog(root: Path, executable: Path) -> Path:
	name = f"{platform_name()}-{architecture_name()}.catalog.yaml"
	catalog = root / name
	catalog.write_text(
		f"{executable.name}: {file_checksum(executable)}\n",
		encoding="utf-8",
	)
	return catalog


def platform_catalog_identity(path: Path) -> tuple[str, str]:
	match = re.fullmatch(
		r"(macos|linux|windows)-(arm64|x64)\.catalog\.yaml",
		path.name,
	)
	if not match:
		raise ValueError(f"Invalid platform catalog name: {path}")
	return match.groups()


def combine_catalogs(
	root: Path,
	output_directory: Path,
	catalog: Path,
	manifest: Path,
	metadata: dict[str, str],
) -> Path:
	releases: list[tuple[str, str, list[tuple[str, str]]]] = []
	for platform_catalog in sorted(root.glob("*.catalog.yaml")):
		if platform_catalog == catalog:
			continue

		opsys, arch = platform_catalog_identity(platform_catalog)
		files: list[tuple[str, str]] = []
		for line in platform_catalog.read_text(encoding="utf-8").splitlines():
			if not line or line.startswith("#") or ":" not in line:
				continue
			name, _, checksum = line.partition(":")
			if name and checksum.strip():
				files.append((name.strip(), checksum.strip()))
		if not files:
			raise ValueError(
				f"The platform catalog has no file checksums: {platform_catalog}"
			)

		releases.append((opsys, arch, files))

	content = catalog.read_text(encoding="utf-8").rstrip("\n")
	fields = {
		"id": metadata["id"],
		"name": metadata["name"],
		"version": metadata["version"],
		"description": metadata["description"],
		"manifest": manifest.name,
		"checksum": file_checksum(manifest),
	}
	for key, value in fields.items():
		field = f"{key}: {value}"
		lines = content.splitlines()
		for index, line in enumerate(lines):
			if line.startswith(f"{key}:"):
				lines[index] = field
				break
		else:
			lines.append(field)
		content = "\n".join(lines)

	build_time = datetime.now()
	content += (
		f"\ndate: {build_time:%Y-%m-%d}\n"
		f"time: {build_time:%H:%M:%S}\n"
		"releases:\n"
	)
	for opsys, arch, files in releases:
		content += f"  - opsys: {opsys}\n"
		content += f"    arch: {arch}\n"
		content += "    artifacts:\n"
		content += "".join(
			f"      - name: {file_name}\n"
			f"        checksum: {checksum}\n"
			for file_name, checksum in files
		)

	output_catalog = output_directory / "catalog.yaml"
	output_catalog.write_text(content, encoding="utf-8")
	return output_catalog


def store_catalog_path() -> Path:
	dev_directory = os.environ.get("DEV")
	if dev_directory:
		return Path(dev_directory).expanduser() / "spore-store" / "store" / "catalog.yaml"

	return Path(__file__).resolve().parents[2].parent / "spore-store" / "store" / "catalog.yaml"


def copy_manifest_to_store(store_catalog: Path, manifest: Path) -> Path:
	destination = store_catalog.parent / "manifests" / manifest.name
	destination.parent.mkdir(parents=True, exist_ok=True)
	shutil.copy2(manifest, destination)
	return destination


def update_store_catalog(
	store_catalog: Path,
	release_catalog: Path,
	node_id: str,
) -> Path:
	if not store_catalog.is_file():
		raise ValueError(f"The store catalog path is not a file: {store_catalog}")

	store_lines = store_catalog.read_text(encoding="utf-8").splitlines()
	release_lines = [
		line
		for line in release_catalog.read_text(encoding="utf-8").splitlines()
		if line.strip()
	]
	if not release_lines:
		raise ValueError(f"The release catalog is empty: {release_catalog}")

	replacement = [f"  - {release_lines[0]}"]
	replacement.extend(f"    {line}" if line else line for line in release_lines[1:])
	entry_starts = [
		index for index, line in enumerate(store_lines) if line.startswith("  - ")
	]
	start = None
	for index in entry_starts:
		end = next(
			(entry for entry in entry_starts if entry > index),
			len(store_lines),
		)
		entry_lines = store_lines[index:end]
		if any(
			re.match(rf"^(?:  - |    )id:\s*{re.escape(node_id)}\s*$", line)
			for line in entry_lines
		):
			start = index
			break

	if start is None:
		store_lines.extend(replacement)
		store_catalog.write_text("\n".join(store_lines) + "\n", encoding="utf-8")
		return store_catalog

	end = next(
		(
			entry
			for entry in entry_starts
			if entry > start
		),
		len(store_lines),
	)
	store_lines[start:end] = replacement
	store_catalog.write_text("\n".join(store_lines) + "\n", encoding="utf-8")
	return store_catalog


def create_archive(output_directory: Path, executable: Path) -> Path:
	name = (
		f"{executable.stem}-{platform_name()}-{architecture_name()}.zip"
	)
	archive = output_directory / name
	with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zip_file:
		for path in sorted(output_directory.rglob("*")):
			if not path.is_file() or path.suffix.lower() == ".zip":
				continue
			zip_file.write(path, path.relative_to(output_directory))
	return archive


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


def commit_and_push_release(
	root: Path,
	manifest: Path,
	catalog: Path,
	platform_catalog: Path,
	version: str,
) -> str:
	repository = Path(run_git(root, "rev-parse", "--show-toplevel")).resolve()
	try:
		manifest_path = manifest.relative_to(repository)
		catalog_path = catalog.relative_to(repository)
		platform_catalog_path = platform_catalog.relative_to(repository)
	except ValueError as error:
		raise ValueError(
			"The manifest and catalogs must be inside the Git repository."
		) from error

	if run_git(repository, "diff", "--cached", "--name-only"):
		raise ValueError("The Git index has staged changes; commit or unstage them first.")

	tag = release_tag(version)
	try:
		run_git(repository, "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}")
	except RuntimeError:
		pass
	else:
		raise ValueError(f"The release tag already exists: {tag}")

	branch = run_git(repository, "branch", "--show-current")
	if not branch:
		raise ValueError("Cannot release from a detached HEAD.")

	run_git(
		repository,
		"add",
		"--",
		str(manifest_path),
		str(catalog_path),
		str(platform_catalog_path),
	)
	run_git(
		repository,
		"commit",
		"-m",
		f"Release {tag}",
		"-m",
		"Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>",
	)
	run_git(repository, "tag", "-a", tag, "-m", f"Release {tag}")
	print(
		"Authenticating with GitHub to push the product branch "
		f"and release tag {tag}."
	)
	run_git(repository, "push", "origin", branch)
	run_git(repository, "push", "origin", tag)
	return tag


def ensure_clean_worktree(root: Path) -> None:
	changes = run_git(root, "status", "--porcelain", "--untracked-files=all")
	if changes:
		raise ValueError(
			"Git worktree has uncommitted changes; commit, stash, or remove them "
			f"before releasing:\n{changes}"
		)


def main() -> int:
	try:
		root = project_root()
		manifest = required_file("manifest", root)
		executable = required_file("executable", root)
		catalog = root / "catalog.yaml"
		if not catalog.is_file():
			raise ValueError(f"The catalog.yaml path is not a file: {catalog}")
		context = root / ".spore.alias.context"
		if not context.is_file():
			raise ValueError(f"The .spore.alias.context path is not a file: {context}")
	except ValueError as error:
		print(error, file=sys.stderr)
		return 2

	try:
		ensure_clean_worktree(root)
	except (OSError, RuntimeError, ValueError) as error:
		print(f"Failed to validate Git worktree: {error}", file=sys.stderr)
		return 1

	try:
		version = increment_manifest_version(manifest)
	except (OSError, UnicodeError, ValueError) as error:
		print(f"Failed to increment manifest version: {error}", file=sys.stderr)
		return 1

	output_directory = root.parent / "dist"
	output_directory.mkdir(parents=True, exist_ok=True)

	print("Release Script")
	print(f"cwd: {root}")
	print(f"output directory: {output_directory}")
	print(f"manifest: {manifest}")
	print(f"executable: {executable}")
	print(f"catalog: {catalog}")
	print(f"context: {context}")
	print(f"manifest version: {version}")

	try:
		metadata = manifest_metadata(manifest)
	except (OSError, UnicodeError, ValueError) as error:
		print(f"Failed to validate manifest: {error}", file=sys.stderr)
		return 1
	if metadata["trust"].strip("'\"") != "developer":
		print(
			"Failed to validate manifest trust: source manifests must use "
			"trust 'developer'.",
			file=sys.stderr,
		)
		return 1

	release_manifest = output_directory / manifest.name
	try:
		shutil.copy2(manifest, release_manifest)
		replace_manifest_trust(release_manifest, RELEASE_TRUST)
		release_metadata = manifest_metadata(release_manifest)
	except OSError as error:
		print(f"Failed to create release manifest: {error}", file=sys.stderr)
		return 1
	except (UnicodeError, ValueError) as error:
		print(f"Failed to update release manifest: {error}", file=sys.stderr)
		return 1
	if release_metadata["trust"].strip("'\"") != RELEASE_TRUST:
		print(
			"Failed to validate release manifest trust: release manifests must use "
			f"trust '{RELEASE_TRUST}'.",
			file=sys.stderr,
		)
		return 1
	print(f"Created release manifest: {release_manifest}")

	try:
		platform_catalog = write_platform_catalog(root, executable)
	except (OSError, UnicodeError, ValueError) as error:
		print(f"Failed to create platform catalog: {error}", file=sys.stderr)
		return 1
	print(f"Wrote executable checksum to {platform_catalog}")

	try:
		output_catalog = combine_catalogs(
			root,
			output_directory,
			catalog,
			release_manifest,
			metadata,
		)
	except (OSError, UnicodeError, ValueError) as error:
		print(f"Failed to create combined catalog: {error}", file=sys.stderr)
		return 1
	print(f"Wrote combined catalog to {output_catalog}")

	try:
		store_catalog = update_store_catalog(
			store_catalog_path(),
			output_catalog,
			metadata["id"],
		)
	except (OSError, UnicodeError, ValueError) as error:
		print(f"Failed to update store catalog: {error}", file=sys.stderr)
		return 1
	print(f"Updated store catalog: {store_catalog}")

	try:
		store_manifest = copy_manifest_to_store(store_catalog, release_manifest)
	except OSError as error:
		print(f"Failed to copy manifest to the store: {error}", file=sys.stderr)
		return 1
	print(f"Copied manifest to {store_manifest}")

	destination = output_directory / executable.name
	try:
		shutil.copy2(executable, destination)
	except OSError as error:
		print(f"Failed to copy executable to {destination}: {error}", file=sys.stderr)
		return 1
	print(f"Copied {executable} to {destination}")

	try:
		archive = create_archive(output_directory, executable)
	except OSError as error:
		print(f"Failed to create release archive: {error}", file=sys.stderr)
		return 1
	print(f"Created release archive: {archive}")

	try:
		tag = commit_and_push_release(
			root,
			manifest,
			catalog,
			platform_catalog,
			version,
		)
	except (OSError, RuntimeError, ValueError) as error:
		print(f"Failed to commit and push release: {error}", file=sys.stderr)
		return 1
	print(f"Committed and pushed release tag: {tag}")

	print(
		f"\nReleased version {version} on "
		f"{platform_name()}-{architecture_name()} successfully."
	)
	print("Run publish after inspecting the artifacts.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
