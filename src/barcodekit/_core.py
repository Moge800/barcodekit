"""Core barcodekit API."""

from __future__ import annotations

import math
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ._binary import resolve_binary
from ._errors import (
    BarcodeKitBinaryNotFound,
    BarcodeKitCommandError,
    BarcodeKitTimeout,
)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_TWO_DIMENSIONAL_LIMITS = {
    "datamatrix": 128,
    "qr": 256,
    "aztec": 256,
    "pdf417": 256,
}
_ONE_DIMENSIONAL = {
    "code128",
    "code39",
    "code93",
    "codabar",
    "itf",
    "code25",
    "ean13",
    "ean8",
}
_SUPPORTED_SYMBOLOGIES = frozenset(_TWO_DIMENSIONAL_LIMITS) | _ONE_DIMENSIONAL
_COMMON_2D_OPTIONS = frozenset({"module", "quiet", "size"})
_COMMON_1D_OPTIONS = frozenset({"module", "height", "quiet", "label"})
_ALLOWED_OPTIONS = {
    "datamatrix": _COMMON_2D_OPTIONS,
    "qr": _COMMON_2D_OPTIONS | {"level"},
    "aztec": _COMMON_2D_OPTIONS,
    "pdf417": {"module", "quiet", "level"},
    "code128": _COMMON_1D_OPTIONS,
    "code39": _COMMON_1D_OPTIONS | {"fullascii"},
    "code93": _COMMON_1D_OPTIONS | {"fullascii"},
    "codabar": _COMMON_1D_OPTIONS,
    "itf": _COMMON_1D_OPTIONS,
    "code25": _COMMON_1D_OPTIONS,
    "ean13": _COMMON_1D_OPTIONS,
    "ean8": _COMMON_1D_OPTIONS,
}
_BASIC_CODE39_CHARACTERS = frozenset("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-. $/+%")
_CODABAR_PATTERN = re.compile(r"^[A-D][0-9\-$:/.+]+[A-D]$")


@dataclass(frozen=True)
class BarcodeImage:
    """A generated PNG image."""

    png: bytes

    def save(self, path: str | Path) -> Path:
        """Write the PNG bytes to path and return the resulting Path."""
        destination = Path(path)
        destination.write_bytes(self.png)
        return destination

    def to_bytes(self) -> bytes:
        """Return the raw PNG bytes."""
        return self.png


def _validate_int(value: object, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    integer = value
    if not minimum <= integer <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return integer


def _validate_bool(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{name} must be a boolean")
    return value


def _validate_qr_level(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("level must be a string for QR codes")
    level = value.upper()
    if level not in {"L", "M", "Q", "H"}:
        raise ValueError("QR level must be one of L, M, Q, or H")
    return level


def _validate_pdf417_level(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError("level must be an integer or numeric string for PDF417")
    if isinstance(value, str):
        if not value.isdigit():
            raise ValueError("PDF417 level must be between 0 and 8")
        value = int(value)
    if not isinstance(value, int):
        raise TypeError("level must be an integer or numeric string for PDF417")
    if not 0 <= value <= 8:
        raise ValueError("PDF417 level must be between 0 and 8")
    return value


def _validate_options(symbology: str, options: Mapping[str, object]) -> dict[str, object]:
    unknown = set(options) - _ALLOWED_OPTIONS[symbology]
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"Unsupported option(s) for {symbology}: {names}")

    if options.get("size") is not None and options.get("module") is not None:
        raise ValueError(
            "size and module cannot be specified together; set size=None to use module"
        )

    validated: dict[str, object] = {}
    for name, value in options.items():
        if value is None:
            continue
        if name == "module":
            validated[name] = _validate_int(value, name, 2, 32)
        elif name == "quiet":
            validated[name] = _validate_int(value, name, 0, 16)
        elif name == "size":
            validated[name] = _validate_int(value, name, 16, 2048)
        elif name == "height":
            validated[name] = _validate_int(value, name, 20, 600)
        elif name in {"label", "fullascii"}:
            validated[name] = _validate_bool(value, name)
        elif name == "level" and symbology == "qr":
            validated[name] = _validate_qr_level(value)
        elif name == "level" and symbology == "pdf417":
            validated[name] = _validate_pdf417_level(value)
    return validated


def _utf8_bytes(text: str) -> bytes:
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("text must be valid UTF-8") from exc


def _validate_ascii(text: str, symbology: str, maximum: int) -> None:
    if not text.isascii():
        raise ValueError(f"{symbology} text must contain ASCII characters only")
    if len(text) > maximum:
        raise ValueError(f"{symbology} text must be at most {maximum} characters")


def _ean_checksum(body: str) -> str:
    total = sum(
        int(digit) * (3 if index % 2 == 0 else 1)
        for index, digit in enumerate(reversed(body))
    )
    return str((10 - total % 10) % 10)


def _validate_text(symbology: str, text: str, options: Mapping[str, object]) -> None:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text:
        raise ValueError("text must not be empty")
    if "\x00" in text:
        raise ValueError("text must not contain NUL characters")

    if symbology in _TWO_DIMENSIONAL_LIMITS:
        maximum = _TWO_DIMENSIONAL_LIMITS[symbology]
        if len(_utf8_bytes(text)) > maximum:
            raise ValueError(f"{symbology} text must be at most {maximum} UTF-8 bytes")
        return

    if symbology == "code128":
        _validate_ascii(text, symbology, 80)
        return

    if symbology in {"code39", "code93"}:
        _validate_ascii(text, symbology, 128)
        if not options.get("fullascii", False) and not set(text) <= _BASIC_CODE39_CHARACTERS:
            raise ValueError(
                f"{symbology} text contains characters that require fullascii=True"
            )
        return

    if symbology == "codabar":
        _validate_ascii(text, symbology, 128)
        if _CODABAR_PATTERN.fullmatch(text) is None:
            raise ValueError(
                "codabar text must start and end with A-D and contain valid data characters"
            )
        return

    if symbology in {"itf", "code25"}:
        _validate_ascii(text, symbology, 128)
        if not text.isdigit():
            raise ValueError(f"{symbology} text must contain digits only")
        if symbology == "itf" and len(text) % 2:
            raise ValueError("itf text must contain an even number of digits")
        return

    required_lengths = (12, 13) if symbology == "ean13" else (7, 8)
    if not text.isascii() or not text.isdigit() or len(text) not in required_lengths:
        lengths = " or ".join(str(length) for length in required_lengths)
        raise ValueError(f"{symbology} text must contain exactly {lengths} digits")
    if len(text) == required_lengths[1] and text[-1] != _ean_checksum(text[:-1]):
        raise ValueError(f"{symbology} text has an invalid check digit")


def _option_flag(name: str) -> str:
    return f"--{name.replace('_', '-')}"


def _build_option_arguments(options: Mapping[str, object]) -> list[str]:
    arguments: list[str] = []
    for name, value in options.items():
        flag = _option_flag(name)
        if isinstance(value, bool):
            if value:
                arguments.append(flag)
        else:
            arguments.extend((flag, str(value)))
    return arguments


def _redact_stderr(stderr: str, text: str) -> str:
    return stderr.replace(text, "<redacted>") if text else stderr


def _is_png(data: bytes) -> bool:
    if not data.startswith(_PNG_SIGNATURE):
        return False

    offset = len(_PNG_SIGNATURE)
    first_chunk = True
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        chunk_type = data[offset + 4 : offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            return False
        if first_chunk and (chunk_type != b"IHDR" or length != 13):
            return False
        first_chunk = False
        if chunk_type == b"IEND":
            return length == 0 and chunk_end == len(data)
        offset = chunk_end
    return False


class BarcodeKit:
    """Generate barcode PNGs by invoking barcode-rest in one-shot CLI mode."""

    def __init__(
        self,
        executable: str | Path | None = None,
        timeout: float = 10.0,
    ) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise TypeError("timeout must be a number")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a finite number greater than zero")
        self._executable = executable
        self.timeout = float(timeout)

    def generate(self, symbology: str, text: str, **options: object) -> BarcodeImage:
        """Generate a barcode using a supported symbology."""
        if not isinstance(symbology, str):
            raise TypeError("symbology must be a string")
        if symbology not in _SUPPORTED_SYMBOLOGIES:
            raise ValueError(f"Unsupported symbology: {symbology}")

        validated_options = _validate_options(symbology, options)
        _validate_text(symbology, text, validated_options)
        executable = resolve_binary(self._executable)
        command = [
            str(executable),
            "generate",
            symbology,
            "--text",
            text,
            "--output",
            "-",
            *_build_option_arguments(validated_options),
        ]

        try:
            completed = subprocess.run(  # noqa: UP022 - explicit PIPEs are part of the contract
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise BarcodeKitTimeout(self.timeout, command) from exc
        except FileNotFoundError as exc:
            raise BarcodeKitBinaryNotFound(
                f"barcode-rest executable disappeared before it could be run: {executable}"
            ) from exc
        except OSError as exc:
            message = _redact_stderr(str(exc), text)
            raise BarcodeKitCommandError(None, command, message) from exc

        stderr = _redact_stderr(completed.stderr.decode("utf-8", errors="replace"), text)
        if completed.returncode != 0:
            raise BarcodeKitCommandError(completed.returncode, command, stderr)
        if not _is_png(completed.stdout):
            raise BarcodeKitCommandError(0, command, "barcode-rest produced invalid PNG output")
        return BarcodeImage(completed.stdout)

    def datamatrix(
        self,
        text: str,
        *,
        size: int | None = 256,
        module: int | None = None,
        quiet: int | None = None,
    ) -> BarcodeImage:
        return self.generate("datamatrix", text, size=size, module=module, quiet=quiet)

    def qr(
        self,
        text: str,
        *,
        size: int | None = 512,
        module: int | None = None,
        quiet: int | None = None,
        level: str = "M",
    ) -> BarcodeImage:
        return self.generate(
            "qr", text, size=size, module=module, quiet=quiet, level=level
        )

    def aztec(
        self,
        text: str,
        *,
        size: int | None = 512,
        module: int | None = None,
        quiet: int | None = None,
    ) -> BarcodeImage:
        return self.generate("aztec", text, size=size, module=module, quiet=quiet)

    def pdf417(
        self,
        text: str,
        *,
        module: int | None = None,
        quiet: int | None = None,
        level: int | str = 2,
    ) -> BarcodeImage:
        return self.generate("pdf417", text, module=module, quiet=quiet, level=level)

    def code128(
        self,
        text: str,
        *,
        module: int | None = None,
        height: int | None = 80,
        quiet: int | None = None,
        label: bool = False,
    ) -> BarcodeImage:
        return self.generate(
            "code128", text, module=module, height=height, quiet=quiet, label=label
        )

    def code39(
        self,
        text: str,
        *,
        module: int | None = None,
        height: int | None = 80,
        quiet: int | None = None,
        label: bool = False,
        fullascii: bool = False,
    ) -> BarcodeImage:
        return self.generate(
            "code39",
            text,
            module=module,
            height=height,
            quiet=quiet,
            label=label,
            fullascii=fullascii,
        )

    def code93(
        self,
        text: str,
        *,
        module: int | None = None,
        height: int | None = 80,
        quiet: int | None = None,
        label: bool = False,
        fullascii: bool = False,
    ) -> BarcodeImage:
        return self.generate(
            "code93",
            text,
            module=module,
            height=height,
            quiet=quiet,
            label=label,
            fullascii=fullascii,
        )

    def codabar(
        self,
        text: str,
        *,
        module: int | None = None,
        height: int | None = 80,
        quiet: int | None = None,
        label: bool = False,
    ) -> BarcodeImage:
        return self.generate(
            "codabar", text, module=module, height=height, quiet=quiet, label=label
        )

    def itf(
        self,
        text: str,
        *,
        module: int | None = None,
        height: int | None = 80,
        quiet: int | None = None,
        label: bool = False,
    ) -> BarcodeImage:
        return self.generate(
            "itf", text, module=module, height=height, quiet=quiet, label=label
        )

    def code25(
        self,
        text: str,
        *,
        module: int | None = None,
        height: int | None = 80,
        quiet: int | None = None,
        label: bool = False,
    ) -> BarcodeImage:
        return self.generate(
            "code25", text, module=module, height=height, quiet=quiet, label=label
        )

    def ean13(
        self,
        text: str,
        *,
        module: int | None = None,
        height: int | None = 80,
        quiet: int | None = None,
        label: bool = False,
    ) -> BarcodeImage:
        return self.generate(
            "ean13", text, module=module, height=height, quiet=quiet, label=label
        )

    def ean8(
        self,
        text: str,
        *,
        module: int | None = None,
        height: int | None = 80,
        quiet: int | None = None,
        label: bool = False,
    ) -> BarcodeImage:
        return self.generate(
            "ean8", text, module=module, height=height, quiet=quiet, label=label
        )
