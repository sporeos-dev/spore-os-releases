#!/usr/bin/env python3
"""Prepare a full Spore OS release for this host: gate, check, build, archive.

Run on each OS you ship. The first run bumps the spored version and pushes it; runs on
other hosts (and reruns before publish) reuse that version. Inspect releases/dist and
release-notes.md, then run publish.py.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import common
from common import (
    COMPONENTS, DIST, INSTALL, SIBLING_ROOT, SPORED_MANIFEST, ReleaseError,
)

PROJECT_DIST = INSTALL / "dist"


def banner(message: str) -> None:
    print(f"\n=====> {message}\n", flush=True)


def determine_version() -> tuple[str, bool]:
    """Returns (version, is_new). A version is joined while this host has not published it."""
    current = common.manifest_version()
    subject = common.run_git(
        SIBLING_ROOT / "spore-os", "log", "-1", "--format=%s", "--", str(SPORED_MANIFEST)
    )
    joining = (
        subject == common.release_subject(current)
        and common.platform_key() not in common.catalog_platforms(current)
    )
    return (current, False) if joining else (common.next_patch(current), True)


def check_tags(version: str, is_new: bool) -> None:
    tag = f"v{version}"
    for name in COMPONENTS:
        repository = SIBLING_ROOT / name
        existing = common.tag_commit(repository, tag)
        if is_new and existing:
            raise ReleaseError(f"{name}: tag {tag} already exists.")
        if not is_new and existing and existing != common.head(repository):
            raise ReleaseError(f"{name}: HEAD is not at {tag}; this host would build different source.")


def run_checks() -> None:
    failures: list[str] = []
    quick = common.REPOSITORY_ROOT / "tools" / "go" / "quick.py"
    for project in common.GO_PROJECTS:
        result = common.run([sys.executable, str(quick)], env={**common.dev_environment(), "cwd": str(SIBLING_ROOT / project)})
        if result.returncode:
            failures.append(project)
    for project in common.C_PROJECTS:
        banner(f"[{project}] make check")
        try:
            result = common.run(["make", "check"], cwd=SIBLING_ROOT / project)
        except OSError:
            print(f"warning: make not found, skipping {project}", file=sys.stderr)
            continue
        if result.returncode:
            failures.append(project)
    if failures:
        raise ReleaseError("Checks failed:\n" + "\n".join(f"- {name}" for name in failures))


def verify_dist(version: str) -> None:
    checksums = PROJECT_DIST / "checksums.sha256"
    if not checksums.is_file():
        raise ReleaseError(f"Build did not produce {checksums}")
    entries = 0
    for line in checksums.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        expected, _, relative = line.partition(" ")
        path = PROJECT_DIST / relative.strip().lstrip("*")
        if not path.is_file() or common.sha256(path) != expected:
            raise ReleaseError(f"dist does not match checksums.sha256: {relative.strip()}")
        entries += 1
    if not entries:
        raise ReleaseError("checksums.sha256 is empty")

    built = common.read_flat_yaml(PROJECT_DIST / "spored.manifest.spore.yaml").get("version")
    if built != version:
        raise ReleaseError(f"dist spored manifest is version {built}, expected {version}")

    installer = "install-machine.ps1" if common.host_platform()[0] == "windows" else "install.sh"
    if not (PROJECT_DIST / installer).is_file():
        raise ReleaseError(f"dist is missing {installer}")


def create_archive() -> Path:
    DIST.mkdir(exist_ok=True)
    archive = DIST / common.asset_name()
    archive.unlink(missing_ok=True)
    if archive.suffix == ".zip":
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zip_file:
            for path in sorted(PROJECT_DIST.rglob("*")):
                if path.is_file():
                    zip_file.write(path, "dist/" + path.relative_to(PROJECT_DIST).as_posix())
    else:
        def normalize(info: tarfile.TarInfo) -> tarfile.TarInfo:
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            return info

        with tarfile.open(archive, "w:gz") as tar:
            tar.add(PROJECT_DIST, arcname="dist", filter=normalize)
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-checks", action="store_true", help="skip the Go and C quick checks")
    arguments = parser.parse_args()

    try:
        banner(f"Gating repositories ({common.platform_key()})")
        common.gate_repositories(fetch=True)

        version, is_new = determine_version()
        check_tags(version, is_new)
        print(f"Spore OS v{version} ({'new release' if is_new else 'joining in-flight release'})")

        if not arguments.skip_checks:
            run_checks()

        spore_os = SIBLING_ROOT / "spore-os"
        if is_new:
            common.set_manifest_version(version)
        try:
            banner("Building")
            if common.run(common.build_command(), env=common.dev_environment()).returncode:
                raise ReleaseError("Build failed.")
            verify_dist(version)
            archive = create_archive()
        except BaseException:
            if is_new:
                common.run_git(spore_os, "checkout", "--", str(SPORED_MANIFEST))
            raise

        if is_new:
            common.commit_and_push(spore_os, [str(SPORED_MANIFEST)], common.release_subject(version))

        common.write_flat_yaml(
            DIST / "release.yaml",
            {
                "version": version,
                "platform": common.platform_key(),
                "asset": archive.name,
                "checksum": f"sha256:{common.sha256(archive)}",
                **{f"commit-{name}": common.head(SIBLING_ROOT / name) for name in COMPONENTS},
            },
        )
        created = common.ensure_notes(is_new)
    except (OSError, ReleaseError) as error:
        print(f"\nRelease failed: {error}", file=sys.stderr)
        return 1

    print(f"\nPrepared v{version} for {common.platform_key()}: {archive}")
    if created:
        print(f"Edit {common.NOTES} (replace the TODO marker).")
    print("Inspect the artifacts, then run publish.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
