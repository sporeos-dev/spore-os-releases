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
PREAMBLE = REPOSITORY_ROOT / "resources" / "preamble.md"
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


# ---------------------------------------------------------------- catalog
# releases/catalog.yaml is read by the website (spore-os-site/releases.html), newest release first:
#
#   releases:
#     - version: 0.2.2
#       tag: v0.2.2
#       state: alpha
#       date: 2026-10-26
#       platforms:
#         - opsys: macos
#           arch: universal
#           name: spore-os-install-macos-universal.tar.gz
#           checksum: sha256:...

def read_catalog() -> list[dict]:
    releases: list[dict] = []
    if not CATALOG.is_file():
        return releases
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "releases:":
            continue
        indent = len(line) - len(line.lstrip())
        if stripped.startswith("- "):
            stripped = stripped[2:]
            if indent == 2:
                releases.append({"platforms": []})
            else:
                releases[-1]["platforms"].append({})
        key, _, value = stripped.partition(":")
        if key == "platforms":
            continue
        target = releases[-1] if indent <= 4 else releases[-1]["platforms"][-1]
        target[key] = value.strip()
    return releases


def write_catalog(releases: list[dict]) -> None:
    lines = ["# Copyright 2026 Matt Harrison", "# SPDX-License-Identifier: Apache-2.0", "", "releases:"]
    for release in releases:
        fields = [(k, v) for k, v in release.items() if k != "platforms"]
        for index, (key, value) in enumerate(fields):
            lines.append(f"{'  - ' if index == 0 else '    '}{key}: {value}")
        lines.append("    platforms:")
        for entry in release["platforms"]:
            for index, (key, value) in enumerate(entry.items()):
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

def notes_stub(version: str) -> str:
    return (
        f"## What's new in {version}\n\n{NOTES_STUB_MARKER}\n\n"
        "## Call-to-action\n"
        "- install using the installation scripts\n"
        "- try some spore calls from the terminal\n"
        "`spore SPORE.help`\n"
        "`spore SPORE.node.list`\n"
        "`spore SPORE.command.list`\n"
        "- open and test Spore Shell (send commands to the hub) and Spore Witness "
        "(watch the inputs and outputs)\n"
    )


def ensure_notes(version: str) -> bool:
    """Create the notes stub unless notes for this version already exist. Returns True if created."""
    if NOTES.is_file() and NOTES.read_text(encoding="utf-8").startswith(f"## What's new in {version}\n"):
        return False
    NOTES.write_text(notes_stub(version), encoding="utf-8")
    return True


def render_release_body(version: str) -> str:
    notes = NOTES.read_text(encoding="utf-8")
    if NOTES_STUB_MARKER in notes:
        raise ReleaseError(f"{NOTES.name} still has the TODO marker; edit it before publishing.")
    if not notes.startswith(f"## What's new in {version}\n"):
        raise ReleaseError(f"{NOTES.name} is not for version {version}; rerun release.")
    return (
        f"# Release v{version}-{STATE}\n\n"
        f"{PREAMBLE.read_text(encoding='utf-8').strip()}\n\n"
        f"{notes.strip()}\n\n"
        "> [!Note]\n"
        "> This repo is a meta-repo for releases only.\n"
        "> Source code found in each repo by following "
        "[this link](https://github.com/sporeos-dev/.github).\n"
    )


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
