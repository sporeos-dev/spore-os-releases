#!/usr/bin/env python3
"""Publish the full Spore OS release prepared by release.py on this host.

Tags the component repositories, creates (or updates) the GitHub release in
spore-os-releases with this host's archive, and records it in releases/catalog.yaml,
which the website reads.
"""

from __future__ import annotations

from datetime import datetime
import sys

import common
from common import (
    COMPONENTS, DIST, NOTES, RELEASES_SLUG, REPOSITORY_ROOT, SIBLING_ROOT, STATE, ReleaseError,
)


def load_release() -> dict[str, str]:
    state_file = DIST / "release.yaml"
    if not state_file.is_file():
        raise ReleaseError(f"{state_file} not found; run release first.")
    state = common.read_flat_yaml(state_file)
    if state.get("platform") != common.platform_key():
        raise ReleaseError(f"The prepared release is for {state.get('platform')}, not this host.")
    if state["version"] != common.manifest_version():
        raise ReleaseError("The spored manifest version changed since release; rerun release.")
    archive = DIST / state["asset"]
    if not archive.is_file() or f"sha256:{common.sha256(archive)}" != state["checksum"]:
        raise ReleaseError(f"{archive} is missing or changed since release; rerun release.")
    return state


def verify_sources(state: dict[str, str]) -> list[str]:
    """Returns the components that still need their version tag."""
    tag = f"v{state['version']}"
    untagged: list[str] = []
    for name in COMPONENTS:
        repository = SIBLING_ROOT / name
        head = common.head(repository)
        if head != state[f"commit-{name}"]:
            raise ReleaseError(f"{name} moved since release; rerun release.")
        existing = common.tag_commit(repository, tag)
        if existing is None:
            untagged.append(name)
    return untagged


def tag_components(names: list[str], version: str) -> None:
    tag = f"v{version}"
    for name in names:
        repository = SIBLING_ROOT / name
        common.run_git(repository, "tag", "-a", tag, "-m", f"Spore OS {tag}")
        common.run_git(repository, "push", "origin", tag)
        print(f"Tagged {name} {tag}")


def gh(*arguments: str, check: bool = True) -> int:
    result = common.run([common.github_cli(), *arguments], capture_output=True)
    if check and result.returncode:
        raise ReleaseError(f"gh {' '.join(arguments[:2])} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.returncode


def publish_github_release(state: dict[str, str], body: str) -> None:
    tag = f"v{state['version']}"
    archive = str(DIST / state["asset"])
    flags = ["--repo", RELEASES_SLUG, "--title", tag, "--notes", body]
    if STATE != "stable":
        flags.append("--prerelease")
    if gh("release", "view", tag, "--repo", RELEASES_SLUG, check=False) == 0:
        gh("release", "edit", tag, *flags)
        gh("release", "upload", tag, archive, "--repo", RELEASES_SLUG, "--clobber")
    else:
        gh("release", "create", tag, archive, *flags, "--target", common.head(REPOSITORY_ROOT))


def merged_catalog(state: dict[str, str]) -> list[dict]:
    opsys, _, arch = state["platform"].partition("-")
    now = datetime.now()
    version = state["version"]
    line_version = ".".join(version.split(".")[:2])
    platform_entry = {
        "opsys": opsys,
        "arch": arch,
        "version": version,
        "date": now.date().isoformat(),
        "time": now.strftime("%H:%M:%S"),
        "name": state["asset"],
        "checksum": state["checksum"],
    }
    releases = common.read_catalog()
    release = next((r for r in releases if r.get("version") == line_version), None)
    if release is None:
        release = {
            "version": line_version,
            "state": STATE,
            "platforms": [],
        }
        releases.insert(0, release)
    release["platforms"] = [
        p
        for p in release["platforms"]
        if (p.get("opsys"), p.get("arch")) != (opsys, arch)
        or common.version_key(p["version"]) > common.version_key(version)
    ]
    release["platforms"].append(platform_entry)
    release["platforms"].sort(
        key=lambda p: (
            tuple(-int(part) for part in p["version"].split(".")),
            p["opsys"],
            p.get("arch", ""),
        )
    )
    return releases


def main() -> int:
    try:
        state = load_release()
        version = state["version"]
        common.gate_repositories(fetch=True)
        untagged = verify_sources(state)
        releases = merged_catalog(state)
        release = next(r for r in releases if r["version"] == ".".join(version.split(".")[:2]))
        body_release = dict(release)
        body_release["version"] = version
        body = common.render_release_body(body_release)
        gh("auth", "status")

        tag_components(untagged, version)
        publish_github_release(state, body)
        common.write_catalog(releases)
        common.commit_and_push(
            REPOSITORY_ROOT,
            [NOTES.name, str(common.CATALOG.relative_to(REPOSITORY_ROOT))],
            f"Publish Spore OS v{version} for {state['platform']}",
        )
    except (OSError, ReleaseError) as error:
        print(f"Publish failed: {error}", file=sys.stderr)
        return 1

    print(f"Published v{version} ({state['platform']}): https://github.com/{RELEASES_SLUG}/releases/tag/v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
