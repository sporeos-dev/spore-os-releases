#!/usr/bin/env python3

import subprocess

TOOLS = (
	("staticcheck", "honnef.co/go/tools/cmd/staticcheck@latest"),
	("golangci-lint", "github.com/golangci/golangci-lint/cmd/golangci-lint@latest"),
	("govulncheck", "golang.org/x/vuln/cmd/govulncheck@latest"),
)


def main() -> None:
	print("==> Updating Homebrew...")
	subprocess.run(["brew", "update"], check=True)
	print("==> Upgrading Go...")
	subprocess.run(["brew", "upgrade", "go"], check=True)

	for name, module in TOOLS:
		print(f"==> Updating {name}...")
		subprocess.run(["go", "install", module], check=True)


if __name__ == "__main__":
	main()