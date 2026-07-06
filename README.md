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

## License

`barcodekit` is MIT licensed. Platform wheels also include the notices and
license texts listed in
[THIRD_PARTY_NOTICES.md](https://github.com/Moge800/barcodekit/blob/v0.1.1/THIRD_PARTY_NOTICES.md).
