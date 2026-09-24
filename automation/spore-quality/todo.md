

## Quality Gates

- [ ] `make check` passes in all modules (build + vet + test)
- [ ] `make analyze` clean — run locally before raising the PR:
- Race detector (`go test -race`)
- Coverage acceptable
- `staticcheck` — no issues
- `golangci-lint` — no issues
- `govulncheck` — no known vulnerabilities

