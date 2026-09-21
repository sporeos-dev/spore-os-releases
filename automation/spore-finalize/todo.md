
# Release finalizer plan
- verify intended branch
- ensure no local release branches
- commit generated
- tag release commit with version
- push commit and tag
- verify downstream repos reference update
- build and zip
- run smoke tests
- publish to github releases (in this repo)?

## Versioning

- [ ] Version bumped in every `*.manifest.spore.yaml` (the `version:` field)
- [ ] All manifests agree on the same version (or have been independently bumped)
- [ ] Git tag created: `git tag vX.Y.Z`

## changelog?