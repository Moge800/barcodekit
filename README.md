# barcodekit

[日本語](https://github.com/Moge800/barcodekit/blob/main/README_JP.md)

`barcodekit` generates barcode PNG images from Python by invoking the local
[`barcode-rest`](https://github.com/Moge800/barcode-rest) executable in its
one-shot CLI mode.

Despite the upstream executable's name, **barcodekit does not start the REST
server and does not use HTTP**. Each operation runs only:

```text
barcode-rest generate <symbology> --text <text> --output -
```

PNG bytes are read from standard output and returned directly to Python.

## Quick start

Install the platform-specific wheel, then:

```python
from barcodekit import code128, datamatrix, qr

datamatrix("ABC123", size=256).save("dm.png")
qr("https://example.com", size=512, level="Q").save("qr.png")
code128("ABC-123456", label=True).save("c128.png")
```

An explicit engine object provides the same methods:

```python
from barcodekit import BarcodeKit

kit = BarcodeKit(timeout=10)
image = kit.datamatrix("ABC123", size=256)

raw_png = image.to_bytes()
image.save("dm.png")
```

For `datamatrix`, `qr`, and `aztec`, `size` and `module` are mutually exclusive.
Set `size=None` when selecting the module size directly:

```python
datamatrix("ABC123", size=None, module=8)
```

## Executable resolution

`barcodekit` resolves the executable when an image is generated, in this order:

1. The file path passed as `BarcodeKit(executable=...)`.
2. The file path in `BARCODEKIT_BINARY`.
3. The executable bundled in the installed platform wheel.

An explicit development binary can be used without building a wheel:

```python
kit = BarcodeKit(executable=r"C:\tools\barcode-rest.exe")
kit.datamatrix("ABC123").save("dm.png")
```

Or with an environment variable:

```powershell
$env:BARCODEKIT_BINARY = "C:\tools\barcode-rest.exe"
uv run python example.py
```

```bash
BARCODEKIT_BINARY=/opt/barcode-rest uv run python example.py
```

These values must be file paths; barcodekit does not search `PATH`.

## Bundled binary wheels

Each released wheel is intended to contain exactly one matching
`barcode-rest` executable. It must not contain a collection of executables for
other operating systems or CPU architectures.

Supported bundled targets:

- Windows amd64
- Linux amd64 using glibc 2.34 or newer, including Ubuntu 22.04 or newer
- Linux arm64 using glibc, including 64-bit Ubuntu and 64-bit Raspberry Pi OS

Unsupported targets:

- macOS
- Windows arm64
- 32-bit Linux and 32-bit Raspberry Pi OS
- musl-based Linux distributions such as Alpine Linux

Binary-free source distributions are not intended for release. On the
supported operating systems and CPU architectures listed above, development
from a source checkout remains supported with `BARCODEKIT_BINARY` or
`BarcodeKit(executable=...)`.

Release builds currently pin
[`barcode-rest` v0.2.0](https://github.com/Moge800/barcode-rest/releases/tag/v0.2.0).
The expected SHA-256 values are committed in `checksums/v0.2.0.sha256`.

## Supported symbologies

Two-dimensional:

- Data Matrix (`datamatrix`)
- QR Code (`qr`)
- Aztec (`aztec`)
- PDF417 (`pdf417`)

One-dimensional:

- Code 128 (`code128`)
- Code 39 (`code39`)
- Code 93 (`code93`)
- Codabar (`codabar`)
- Interleaved 2 of 5 (`itf`)
- Standard 2 of 5 (`code25`)
- EAN-13 / JAN (`ean13`)
- EAN-8 (`ean8`)

`barcodekit` validates supported options, numeric ranges, text limits, basic
character sets, and check digits before starting the executable. Encoding
constraints that depend on the generated symbol remain the responsibility of
`barcode-rest`.

## Security and privacy

- No executable or other data is downloaded at runtime.
- No server is started.
- The REST API and HTTP are not used.
- No outbound network connection is made by the wrapper.
- Barcode text is passed only to the local `barcode-rest` executable.
- The wrapper does not log barcode text.
- Commands shown by wrapper exceptions replace the value after `--text` with
  `<redacted>`. Matching text returned on stderr is also redacted.

The text is necessarily passed through the local process command line because
that is the upstream CLI interface. It may therefore be temporarily visible to
users or tools with permission to inspect local process arguments.

## Development with uv

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy src/barcodekit
uv build
```

Unit tests mock `subprocess.run` and do not need the Go executable. If
`BARCODEKIT_BINARY` is set, the optional integration test generates a real
Data Matrix image and checks its PNG output.

## Preparing a platform wheel

Actual executables are not committed to this repository. Copy one trusted
binary into the package before building:

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
smoke test when `--expected-version` is supplied, removes a stale executable
for another operating system, uses the platform's required filename, and sets
executable bits for Linux targets.

A release build must run on the target architecture and verify all of the
following before its wheel is retained:

1. The binary SHA-256 matches the value pinned for the selected upstream
   `barcode-rest` release.
2. `barcode-rest -version` reports that pinned release.
3. A one-shot Data Matrix command exits successfully and returns a valid PNG.
4. The wheel contains exactly one executable.
5. The wheel has the correct platform tag. Linux tags must reflect the actual
   glibc requirement of the binary.

Do not upload Hatchling's initial `py3-none-any` wheel after inserting a binary;
the release job must apply the verified platform tag first.

## Releasing

`.github/workflows/release.yml` builds these three platform wheels on native
GitHub-hosted runners. For each target it:

1. Downloads the pinned `barcode-rest` release asset.
2. Verifies its committed SHA-256, reported version, and real PNG output.
3. Builds and applies the target-specific wheel tag.
4. Verifies that the wheel contains one matching binary, `py.typed`, and all
   required license notices.

A manual `workflow_dispatch` run builds wheel artifacts for inspection and
never publishes them. Pull requests that change release inputs also build all
three wheels without publishing.

Publishing a GitHub Release whose tag is `v<major>.<minor>.<patch>` first
requires that tag to point exactly to the current default branch head. The
workflow checks out the tag commit, synchronizes `pyproject.toml`,
`src/barcodekit/_version.py`, `uv.lock`, and the versioned notice links, then
commits the metadata update to the default branch as a fast-forward. All three
wheels are built from that exact synchronized commit and published through
PyPI Trusted Publishing. If the tag and default branch differ, the release
stops before building anything. After PyPI succeeds, the wheels are also
attached to the GitHub Release. Pushing a tag by itself does not publish the
package.

The GitHub `pypi` environment and PyPI trusted publisher must be configured
before the first release.

## License

`barcodekit` is MIT licensed. Platform wheels also include the notices and
license texts listed in
[THIRD_PARTY_NOTICES.md](https://github.com/Moge800/barcodekit/blob/v0.0.1/THIRD_PARTY_NOTICES.md).
