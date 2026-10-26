# spore-os-releases
Spore OS is a mulit-repo project.  This acts as a central release repo.


## Releasing Spore OS
Run on each OS you ship (macOS, Linux, Windows), from `tools/hub`:

1. `release.py` gates the component repos, runs the checks, builds `spore-install/dist`, and archives it into `dist/`. The first host bumps the `spored` manifest version and pushes it; other hosts reuse it.
2. Inspect `dist/` and edit `release-notes.md`.
3. `publish.py` tags the component repos, creates or updates the GitHub release, and updates `releases/catalog.yaml`, which the website reads.
