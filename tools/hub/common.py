"""Shared helpers for the full Spore OS release (release.py and publish.py)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repositories import REPOSITORY_ROOT, SIBLING_ROOT, git, tracking_status  # noqa: E402

COAUTHOR = "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
RELEASES_SLUG = "sporeos-dev/spore-os-releases"
STATE = "alpha"

DIST = REPOSITORY_ROOT / "dist"
CATALOG = REPOSITORY_ROOT / "releases" / "catalog.yaml"
NOTES = REPOSITORY_ROOT / "release-notes.md"
NOTES_TEMPLATE = REPOSITORY_ROOT / "release-notes-template.md"
NOTES_STUB_MARKER = "<!-- TODO: replace this line with the release notes, then delete this marker -->"

INSTALL = SIBLING_ROOT / "spore-install"
SPORED_MANIFEST = SIBLING_ROOT / "spore-os" / "spored" / "spored.manifest.spore.yaml"

# Repositories that feed the build; each one must be clean and pushed, and is tagged on publish.
COMPONENTS = (
    "spore-os",
    "spore-client-libs",
    "spore-core-nodes",
    "spore-dialog",
    "spore-hyphae",
    "spore-store",
    "spore-install",
)
# The release repo itself may only carry the generated notes while a release is in flight.
RELEASES_ALLOWED_DIRTY = {"release-notes.md"}

GO_PROJECTS = (
    "spore-os/spored",
    "spore-client-libs/spore_go",
    "spore-core-nodes/spore",
    "spore-core-nodes/spore-log",
    "spore-core-nodes/spore-shell",
    "spore-core-nodes/spore-witness",
    "spore-hyphae/hyphae",
    "spore-dialog/spore-dialog",
    "spore-store/store",
)
C_PROJECTS = (
    "spore-client-libs/parser",
    "spore-client-libs/spore_c",
)


class ReleaseError(Exception):
    pass


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


# ---------------------------------------------------------------- platform

def host_platform() -> tuple[str, str]:
    opsys = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(platform.system())
    if opsys is None:
        raise ReleaseError(f"Unsupported operating system: {platform.system()}")
    if opsys == "macos":
        return opsys, "universal"
    arch = {"aarch64": "arm64", "arm64": "arm64", "x86_64": "x64", "amd64": "x64"}.get(
        platform.machine().lower()
    )
    if arch is None:
        raise ReleaseError(f"Unsupported architecture: {platform.machine()}")
    return opsys, arch


def platform_key() -> str:
    return "-".join(host_platform())


def asset_name() -> str:
    extension = "zip" if host_platform()[0] == "windows" else "tar.gz"
    return f"spore-os-install-{platform_key()}.{extension}"


def build_command() -> list[str]:
    opsys, _ = host_platform()
    if opsys == "windows":
        script = INSTALL / "windows" / "build.ps1"
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    return ["bash", str(INSTALL / opsys / "build.sh")]


# ---------------------------------------------------------------- files

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_flat_yaml(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(("#", " ")) and ":" in line:
            key, _, value = line.partition(":")
            values[key.strip()] = value.strip()
    return values


def write_flat_yaml(path: Path, values: dict[str, str]) -> None:
    path.write_text("".join(f"{key}: {value}\n" for key, value in values.items()), encoding="utf-8")


# ---------------------------------------------------------------- git

def run_git(repository: Path, *arguments: str) -> str:
    result = git(repository, *arguments)
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip() or "failed"
        raise ReleaseError(f"{repository.name}: git {' '.join(arguments)}: {message}")
    return result.stdout.strip()


def head(repository: Path) -> str:
    return run_git(repository, "rev-parse", "HEAD")


def dirty_paths(repository: Path) -> set[str]:
    result = git(repository, "status", "--porcelain=v1", "--untracked-files=all")
    if result.returncode:
        raise ReleaseError(f"{repository.name}: git status failed: {result.stderr.strip()}")
    return {line[3:].split(" -> ")[-1] for line in result.stdout.splitlines()}


def commit_and_push(repository: Path, paths: list[str], message: str) -> None:
    run_git(repository, "add", "--", *paths)
    run_git(repository, "commit", "-m", message, "-m", COAUTHOR)
    run_git(repository, "push", "origin", run_git(repository, "branch", "--show-current"))


def tag_commit(repository: Path, tag: str) -> str | None:
    result = git(repository, "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def gate_repositories(fetch: bool) -> None:
    """Every component must be clean, on a branch, and fully in sync with its upstream."""
    problems: list[str] = []
    for name in (*COMPONENTS, REPOSITORY_ROOT.name):
        repository = SIBLING_ROOT / name
        if not (repository / ".git").exists():
            problems.append(f"{name}: repository not found at {repository}")
            continue
        if fetch:
            result = git(repository, "fetch", "--all", "--prune", "--tags")
            if result.returncode:
                problems.append(f"{name}: fetch failed: {result.stderr.strip()}")
                continue
        allowed = RELEASES_ALLOWED_DIRTY if repository == REPOSITORY_ROOT else set()
        changes = dirty_paths(repository) - allowed
        if changes:
            problems.append(f"{name}: uncommitted changes: {', '.join(sorted(changes))}")
        tracking = tracking_status(repository)
        if tracking is None:
            problems.append(f"{name}: detached HEAD")
        elif tracking.upstream == "—":
            problems.append(f"{name}: branch {tracking.branch} has no upstream")
        elif tracking.ahead or tracking.behind:
            problems.append(
                f"{name}: {tracking.branch} is ahead {tracking.ahead}, behind {tracking.behind}"
            )
    if problems:
        raise ReleaseError("Repository gate failed:\n" + "\n".join(f"- {p}" for p in problems))


# ---------------------------------------------------------------- version

VERSION_LINE = re.compile(r"^version:\s*(\d+)\.(\d+)\.(\d+)\s*$", re.MULTILINE)


def manifest_version() -> str:
    match = VERSION_LINE.search(SPORED_MANIFEST.read_text(encoding="utf-8"))
    if not match:
        raise ReleaseError(f"No a.b.c version in {SPORED_MANIFEST}")
    return ".".join(match.groups())


def set_manifest_version(version: str) -> None:
    text = SPORED_MANIFEST.read_text(encoding="utf-8")
    SPORED_MANIFEST.write_text(VERSION_LINE.sub(f"version: {version}", text, count=1), encoding="utf-8")


def next_patch(version: str) -> str:
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def release_subject(version: str) -> str:
    return f"Release v{version}"


def release_line(version: str) -> str:
    return ".".join(version.split(".")[:2])


def release_tag(line_version: str) -> str:
    """Git tag of a major.minor release line: v0.1.0 for the first line, v<major>.<minor> after."""
    return "v0.1.0" if line_version == "0.1" else f"v{line_version}"


# ---------------------------------------------------------------- catalog
# releases/catalog.yaml is read by the website (spore-os-site/releases.html), newest release line first:
#
#   releases:
#     - version: 0.2
#       tag: v0.2
#       state: alpha
#       platforms:
#         - opsys: macos
#           arch: universal
#           version: 0.2.2
#           date: 2026-10-26
#           time: 12:34:56
#           name: spore-os-install-macos-universal.tar.gz
#           checksum: sha256:...

def read_catalog() -> list[dict]:
    entries: list[dict] = []
    if not CATALOG.is_file():
        return entries
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "releases:":
            continue
        indent = len(line) - len(line.lstrip())
        if stripped.startswith("- "):
            stripped = stripped[2:]
            if indent == 2:
                entries.append({"platforms": []})
            else:
                entries[-1]["platforms"].append({})
        key, _, value = stripped.partition(":")
        if key == "platforms":
            continue
        target = entries[-1] if indent <= 4 else entries[-1]["platforms"][-1]
        target[key] = value.strip()

    releases: list[dict] = []
    by_line: dict[str, dict] = {}
    for entry in entries:
        version = entry.get("version")
        if not version:
            continue
        line_version = ".".join(version.split(".")[:2])
        release = by_line.get(line_version)
        if release is None:
            release = {
                "version": line_version,
                "tag": entry.get("tag") or release_tag(line_version),
                "state": entry.get("state", STATE),
                "platforms": [],
            }
            by_line[line_version] = release
            releases.append(release)
        for platform_entry in entry["platforms"]:
            normalized = dict(platform_entry)
            normalized.setdefault("version", version)
            if entry.get("date"):
                normalized.setdefault("date", entry["date"])
            if entry.get("time"):
                normalized.setdefault("time", entry["time"])
            key = (
                normalized.get("opsys"),
                normalized.get("arch", ""),
            )
            existing = next(
                (
                    platform
                    for platform in release["platforms"]
                    if (platform.get("opsys"), platform.get("arch", "")) == key
                ),
                None,
            )
            if existing is None or version_key(normalized["version"]) >= version_key(existing["version"]):
                release["platforms"] = [
                    platform
                    for platform in release["platforms"]
                    if (platform.get("opsys"), platform.get("arch", "")) != key
                ]
                release["platforms"].append(normalized)
    return releases


def write_catalog(releases: list[dict]) -> None:
    lines = ["# Copyright 2026 Matt Harrison", "# SPDX-License-Identifier: Apache-2.0", "", "releases:"]
    for release in releases:
        fields = [
            (key, release[key])
            for key in ("version", "tag", "state")
            if key in release
        ]
        for index, (key, value) in enumerate(fields):
            lines.append(f"{'  - ' if index == 0 else '    '}{key}: {value}")
        lines.append("    platforms:")
        for entry in sorted(
            release["platforms"],
            key=lambda platform: (tuple(-int(part) for part in platform["version"].split(".")), platform["opsys"]),
        ):
            fields = [
                (key, entry[key])
                for key in ("opsys", "arch", "version", "date", "time", "name", "checksum")
                if key in entry
            ]
            for index, (key, value) in enumerate(fields):
                lines.append(f"{'      - ' if index == 0 else '        '}{key}: {value}")
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def catalog_platforms(version: str) -> set[str]:
    for release in read_catalog():
        if release.get("version") == version:
            return {
                "-".join(p[k] for k in ("opsys", "arch") if p.get(k)) for p in release["platforms"]
            }
    return set()


# ---------------------------------------------------------------- release notes

def notes_stub() -> str:
    return (
        "## Call to action\n\n"
        "- Install using the installation scripts.\n"
        "- Try some spore calls from the terminal: `spore SPORE.help`, `spore SPORE.node.list`, "
        "`spore SPORE.command.list`.\n"
        "- Open Spore Shell (send commands to the hub) and Spore Witness (watch the inputs and outputs).\n\n"
        "## Changes\n\n"
        f"{NOTES_STUB_MARKER}\n"
    )


def ensure_notes() -> bool:
    """Write the notes stub only when release-notes.md does not exist."""
    if NOTES.is_file():
        return False
    NOTES.write_text(notes_stub(), encoding="utf-8")
    return True


def checksum_lines(release: dict) -> list[str]:
    """`shasum -c` lines (`<hex>  <name>`) for every archive in a catalog release."""
    return sorted(
        f"{p['checksum'].removeprefix('sha256:')}  {p['name']}" for p in release["platforms"]
    )


def render_release_body(release: dict) -> str:
    """Fill release-notes-template.md; {{ release_notes }} is the hand-written release-notes.md."""
    notes = NOTES.read_text(encoding="utf-8")
    if NOTES_STUB_MARKER in notes:
        raise ReleaseError(f"{NOTES.name} still has the TODO marker; edit it before publishing.")
    template = NOTES_TEMPLATE.read_text(encoding="utf-8")
    values = {
        "name": "Spore OS",
        "version": release["version"],
        "state": release["state"],
        "platforms": "\n".join(
            f"- `{'-'.join(p[k] for k in ('opsys', 'arch') if p.get(k))}`" for p in release["platforms"]
        ),
        "release_notes": notes.strip(),
        "checksums": "\n".join(checksum_lines(release)),
    }
    for key, value in values.items():
        template = template.replace(f"{{{{ {key} }}}}", value)
    if "{{" in template:
        raise ReleaseError(f"{NOTES_TEMPLATE.name} has an unknown placeholder.")
    return template


# ---------------------------------------------------------------- misc

def run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, text=True, **kwargs)


def dev_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["DEV"] = str(SIBLING_ROOT)
    return environment


def github_cli() -> str:
    for candidate in (shutil.which("gh"), "/opt/homebrew/bin/gh", "/usr/local/bin/gh"):
        if candidate and Path(candidate).is_file():
            return candidate
    raise ReleaseError("Could not find the GitHub CLI (gh).")
