"""Generate barcode PNGs with the local barcode-rest CLI."""

from __future__ import annotations

from pathlib import Path

from ._core import BarcodeImage, BarcodeKit
from ._errors import (
    BarcodeKitBatchError,
    BarcodeKitBinaryNotFound,
    BarcodeKitCommandError,
    BarcodeKitError,
    BarcodeKitTimeout,
    BarcodeKitUnsupportedPlatform,
)
from ._version import __version__

_default_kit = BarcodeKit()


def barcodekit(
    *,
    executable: str | Path | None = None,
    timeout: float = 10.0,
    server: bool = False,
) -> BarcodeKit:
    return BarcodeKit(executable=executable, timeout=timeout, server=server)


def generate(symbology: str, text: str, **options: object) -> BarcodeImage:
    return _default_kit.generate(symbology, text, **options)


def datamatrix(
    text: str,
    *,
    size: int | None = 256,
    module: int | None = None,
    quiet: int | None = None,
) -> BarcodeImage:
    return _default_kit.datamatrix(text, size=size, module=module, quiet=quiet)


def qr(
    text: str,
    *,
    size: int | None = 512,
    module: int | None = None,
    quiet: int | None = None,
    level: str = "M",
) -> BarcodeImage:
    return _default_kit.qr(text, size=size, module=module, quiet=quiet, level=level)


def aztec(
    text: str,
    *,
    size: int | None = 512,
    module: int | None = None,
    quiet: int | None = None,
) -> BarcodeImage:
    return _default_kit.aztec(text, size=size, module=module, quiet=quiet)


def pdf417(
    text: str,
    *,
    module: int | None = None,
    quiet: int | None = None,
    level: int | str = 2,
) -> BarcodeImage:
    return _default_kit.pdf417(text, module=module, quiet=quiet, level=level)


def code128(
    text: str,
    *,
    module: int | None = None,
    height: int | None = 80,
    quiet: int | None = None,
    label: bool = False,
) -> BarcodeImage:
    return _default_kit.code128(
        text, module=module, height=height, quiet=quiet, label=label
    )


def code39(
    text: str,
    *,
    module: int | None = None,
    height: int | None = 80,
    quiet: int | None = None,
    label: bool = False,
    fullascii: bool = False,
) -> BarcodeImage:
    return _default_kit.code39(
        text,
        module=module,
        height=height,
        quiet=quiet,
        label=label,
        fullascii=fullascii,
    )


def code93(
    text: str,
    *,
    module: int | None = None,
    height: int | None = 80,
    quiet: int | None = None,
    label: bool = False,
    fullascii: bool = False,
) -> BarcodeImage:
    return _default_kit.code93(
        text,
        module=module,
        height=height,
        quiet=quiet,
        label=label,
        fullascii=fullascii,
    )


def codabar(
    text: str,
    *,
    module: int | None = None,
    height: int | None = 80,
    quiet: int | None = None,
    label: bool = False,
) -> BarcodeImage:
    return _default_kit.codabar(
        text, module=module, height=height, quiet=quiet, label=label
    )


def itf(
    text: str,
    *,
    module: int | None = None,
    height: int | None = 80,
    quiet: int | None = None,
    label: bool = False,
) -> BarcodeImage:
    return _default_kit.itf(
        text, module=module, height=height, quiet=quiet, label=label
    )


def code25(
    text: str,
    *,
    module: int | None = None,
    height: int | None = 80,
    quiet: int | None = None,
    label: bool = False,
) -> BarcodeImage:
    return _default_kit.code25(
        text, module=module, height=height, quiet=quiet, label=label
    )


def ean13(
    text: str,
    *,
    module: int | None = None,
    height: int | None = 80,
    quiet: int | None = None,
    label: bool = False,
) -> BarcodeImage:
    return _default_kit.ean13(
        text, module=module, height=height, quiet=quiet, label=label
    )


def ean8(
    text: str,
    *,
    module: int | None = None,
    height: int | None = 80,
    quiet: int | None = None,
    label: bool = False,
) -> BarcodeImage:
    return _default_kit.ean8(
        text, module=module, height=height, quiet=quiet, label=label
    )


__all__ = [
    "BarcodeImage",
    "BarcodeKit",
    "BarcodeKitBatchError",
    "BarcodeKitBinaryNotFound",
    "BarcodeKitCommandError",
    "BarcodeKitError",
    "BarcodeKitTimeout",
    "BarcodeKitUnsupportedPlatform",
    "__version__",
    "aztec",
    "barcodekit",
    "codabar",
    "code25",
    "code39",
    "code93",
    "code128",
    "datamatrix",
    "ean8",
    "ean13",
    "generate",
    "itf",
    "pdf417",
    "qr",
]
