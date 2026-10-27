# spore-os-releases
Spore OS is a mulit-repo project.  This acts as a central release repo.


## Releasing Spore OS
Run on each OS you ship (macOS, Linux, Windows), from `tools/hub`:

1. `release.py` gates the component repos, runs the checks, builds `spore-install/dist`, and archives it into `dist/`. Every run increments and pushes the `spored` patch version, so each host build has its own version and can include changes since the previous build.
2. Inspect `dist/` and edit `release-notes.md`. It is only the hand-written update; `release-notes-template.md` supplies the rest of the GitHub release body, as in foundry-releases.
3. `publish.py` tags the component repos with the full patch version, creates or updates the shared `major.minor` GitHub release (for example, `v0.2`), and updates `releases/catalog.yaml`, which the website reads. This allows platform builds such as `0.2.3`, `0.2.4`, and `0.2.5` to appear in one release.
