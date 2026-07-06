# Releasing barcodekit

[日本語](RELEASING_JP.md)

This document is for package maintainers. User-facing installation, supported
platforms, and API usage remain in `README.md`.

## Prerequisites

- Use `uv` for the development and build environment.
- Keep the upstream `barcode-rest` version pinned in
  `.github/workflows/release.yml`.
- Commit the trusted release asset SHA-256 values to
  `checksums/<barcode-rest-version>.sha256`.
- Configure the GitHub `pypi` environment and the PyPI Trusted Publisher before
  the first release.

Actual executables are not committed to this repository. Release jobs download
the pinned assets from the upstream `barcode-rest` GitHub Release.

## Local verification

Run the complete local checks before creating a release:

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy src/barcodekit
uv build
```

## Preparing a platform wheel

To inspect a wheel locally, copy one trusted binary into the package before
building:

```bash
uv run python scripts/prepare_binary.py \
  --binary ./dist/barcode-rest.exe \
  --target windows-amd64 \
  --sha256 <trusted-sha256> \
  --expected-version <pinned-version>

uv run python scripts/prepare_binary.py \
  --binary ./dist/barcode-rest-linux-amd64 \
  --target linux-amd64 \
  --sha256 <trusted-sha256> \
  --expected-version <pinned-version>

uv run python scripts/prepare_binary.py \
  --binary ./dist/barcode-rest-linux-arm64 \
  --target linux-arm64 \
  --sha256 <trusted-sha256> \
  --expected-version <pinned-version>
```

The script rejects a checksum or version mismatch, runs a native one-shot PNG
smoke test, removes stale executables for other operating systems, uses the
target platform's required filename, and sets executable bits for Linux.

A release build must run on the target architecture and verify all of the
following before retaining its wheel:

1. The binary SHA-256 matches the committed value.
2. `barcode-rest -version` reports the pinned release.
3. A one-shot Data Matrix command returns a valid PNG.
4. The wheel contains exactly one matching executable.
5. The wheel has the correct platform tag.
6. The wheel contains `py.typed` and all required license notices.

Do not upload Hatchling's initial `py3-none-any` wheel after inserting a binary.
The release job must apply and verify the platform tag first. Source
distributions are not published.

## CI behavior

`.github/workflows/release.yml` builds these wheels on native GitHub-hosted
runners:

- `win_amd64`
- `manylinux_2_34_x86_64`
- `manylinux_2_17_aarch64`

Pull requests that change release inputs build and verify all three wheels
without publishing. A manual `workflow_dispatch` run also produces inspection
artifacts only.

## Publishing

1. Ensure all intended changes are committed to the default branch.
2. Create `v<major>.<minor>.<patch>` at the current default branch HEAD.
3. Publish the corresponding GitHub Release.
4. Confirm that PyPI publishing and GitHub Release asset attachment succeed.

Pushing a tag alone does not publish the package.

On a published GitHub Release, the workflow:

1. Checks out the release tag.
2. Requires the tag commit to exactly match the current default branch HEAD.
3. Synchronizes the package version in `pyproject.toml`,
   `src/barcodekit/_version.py`, `uv.lock`, and versioned notice links.
4. Commits that metadata-only update to the default branch as a fast-forward.
5. Builds all three wheels from the same synchronized commit.
6. Publishes through PyPI Trusted Publishing.
7. Attaches the wheels to the GitHub Release after PyPI succeeds.

If the tag and default branch HEAD differ, the workflow stops before building
anything. Move or recreate the tag at the current default branch HEAD before
publishing the Release. Do not bypass this check by building the default branch:
doing so could publish code that is not represented by the release tag.
