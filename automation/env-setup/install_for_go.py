import subprocess

TOOLS = (
	("staticcheck", "honnef.co/go/tools/cmd/staticcheck@latest"),
	("golangci-lint", "github.com/golangci/golangci-lint/cmd/golangci-lint@latest"),
	("govulncheck", "golang.org/x/vuln/cmd/govulncheck@latest"),
)

def install_for_go() -> None:
	for name, module in TOOLS:
		print(f"\n==> Installing {name}...\n")
		subprocess.run(["go", "install", module], check=True)

	print("==> Done. Ensure Go bin directory is on your PATH.")