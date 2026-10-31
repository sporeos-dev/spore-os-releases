# {{ name }} v{{ version }}-{{ state }}

> For project overview, contributing guidelines, code of conduct, security policy,
> and licensing information, see the
> [sporeos-dev organization README](https://github.com/sporeos-dev/.github).

## Release status

**{{ state }} software:** This release may change incompatibly between versions.
Review the release notes and use it in environments appropriate for its current
stability level.

## Release update

{{ release_notes }}

## Available downloads

This release currently provides builds for:

{{ platforms }}

Each archive contains the `dist/` install tree for that platform, including
`checksums.sha256` for every installed file. Run the installer from inside it.

## Verify your download

Check the archive against `SHA256SUMS` (attached to this release) before running
the installer:

```sh
shasum -a 256 -c SHA256SUMS --ignore-missing   # macOS / Linux
Get-FileHash .\<archive>                        # Windows PowerShell; compare to the list below
```

```
{{ checksums }}
```

> [!Note]
> This repo is a meta-repo for releases only.
> Source code is found in each repo by following
> [this link](https://github.com/sporeos-dev/.github).
