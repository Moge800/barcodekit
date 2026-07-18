# barcodekit

[日本語](https://github.com/Moge800/barcodekit/blob/main/README_JP.md)

`barcodekit` generates barcode PNG images from Python by invoking the local
[`barcode-rest`](https://github.com/Moge800/barcode-rest) executable in its
one-shot CLI mode.

Despite the upstream executable's name, barcodekit's default mode **does not
start the REST server and does not use HTTP**. Each default-mode operation runs
only:

```text
barcode-rest generate <symbology> --text <text> --output -
```

PNG bytes are read from standard output and returned directly to Python.

For bulk generation, `BarcodeKit(server=True)` can opt in to a local resident
server. This starts the bundled `barcode-rest` process on `127.0.0.1` for the
life of the context manager, passes a generated `-exit-token`, and sends
requests to that local process only.

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

For many images, use server mode to avoid starting a new process for every
barcode:

```python
from barcodekit import barcodekit

with barcodekit(server=True) as kit:
    for index in range(1000):
        kit.datamatrix(f"ITEM-{index:04d}", size=256).save(f"dm-{index:04d}.png")
```

The class form is equivalent:

```python
from barcodekit import BarcodeKit

with BarcodeKit(server=True) as kit:
    image = kit.qr("https://example.com")
```

### Parallel bulk generation

Resident server mode can generate independent images concurrently. Results
from `generate_many()` remain in the same order as the input values:

```python
from barcodekit import barcodekit

values = [f"ITEM-{index:06d}" for index in range(10_000)]

with barcodekit(server=True) as kit:
    images = kit.generate_many("datamatrix", values, workers=8, size=256)
```

For large or streaming inputs, `imap()` keeps at most twice the configured
worker count queued and yields images in input order:

```python
with barcodekit(server=True) as kit:
    for index, image in enumerate(
        kit.imap("qr", values, workers=8, size=256, level="M")
    ):
        image.save(f"qr-{index:06d}.png")
```

Parallel generation requires `server=True`. If `workers` is omitted,
barcodekit uses the detected CPU count, capped at 8. More workers are not
always faster, so benchmark the intended barcode type and host. If an item
fails, `BarcodeKitBatchError.index` identifies its zero-based input position
without including the input text in the error message.

For `datamatrix`, `qr`, and `aztec`, `size` and `module` are mutually exclusive.
Set `size=None` when selecting the module size directly:

```python
datamatrix("ABC123", size=None, module=8)
```

## Using the PNG with Pillow or OpenCV

`barcodekit` does not depend on Pillow, OpenCV, or NumPy. If your application
already uses those libraries, optional helpers can convert the returned PNG
bytes:

```python
from barcodekit import qr

pil_image = qr("ABC123").to_pillow()
```

```python
from barcodekit import qr

cv_image = qr("ABC123").to_cv2()
```

`to_pillow()` requires Pillow at call time. `to_cv2()` requires OpenCV and
NumPy at call time. These packages are not installed by barcodekit.

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
- macOS 12 or newer on Intel Macs
- macOS 12 or newer on Apple Silicon Macs

Unsupported targets:

- Windows arm64
- 32-bit Linux and 32-bit Raspberry Pi OS
- musl-based Linux distributions such as Alpine Linux

Binary-free source distributions are not intended for release. On the
supported operating systems and CPU architectures listed above, development
from a source checkout remains supported with `BARCODEKIT_BINARY` or
`BarcodeKit(executable=...)`.

Release builds currently pin
[`barcode-rest` v0.3.0](https://github.com/Moge800/barcode-rest/releases/tag/v0.3.0).
The expected SHA-256 values are committed in `checksums/v0.3.0.sha256`.

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
- By default, no server is started and the REST API / HTTP are not used.
- `server=True` starts a local `barcode-rest` process bound to `127.0.0.1` and
  uses HTTP only between Python and that local process.
- In server mode, barcodekit starts `barcode-rest` with a generated
  `-exit-token` and uses it only for `POST /exit` when the context manager is
  closed.
- No outbound network connection is made by the wrapper.
- Barcode text is passed only to the local `barcode-rest` executable.
- The wrapper does not log barcode text.
- Commands shown by wrapper exceptions replace the value after `--text` with
  `<redacted>`. Matching text returned on stderr is also redacted.

In default CLI mode, the text is necessarily passed through the local process
command line because that is the upstream CLI interface. It may therefore be
temporarily visible to users or tools with permission to inspect local process
arguments. In `server=True` mode, the text is sent in HTTP query strings only to
the local `127.0.0.1` process; barcode-rest logs paths only and does not log
query values.

## Development with uv

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy src/barcodekit
uv build
```

Run the dependency-free benchmark to compare one-shot CLI generation with
resident server worker counts on the current machine:

```bash
uv run python scripts/benchmark.py --count 200 --workers 1 2 4 8
```

The benchmark reports median batch latency, p95 batch latency, and images per
second. Performance values are environment-specific and are not CI pass/fail
criteria.

Unit tests mock `subprocess.run` and do not need the Go executable. If
`BARCODEKIT_BINARY` is set, the optional integration test generates a real
Data Matrix image and checks its PNG output.

## License

`barcodekit` is licensed under the Apache License 2.0. Platform wheels also
include the notices and license texts listed in
[THIRD_PARTY_NOTICES.md](https://github.com/Moge800/barcodekit/blob/v0.1.2/THIRD_PARTY_NOTICES.md).
