"""Core barcodekit API."""

from __future__ import annotations

import math
import re
import secrets
import socket
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from io import BytesIO
from pathlib import Path
from types import TracebackType
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ._binary import resolve_binary
from ._errors import (
    BarcodeKitBinaryNotFound,
    BarcodeKitCommandError,
    BarcodeKitTimeout,
)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_LOCALHOST = "127.0.0.1"
_TWO_DIMENSIONAL_LIMITS = {
    "datamatrix": 3116,
    "qr": 7089,
    "aztec": 3748,
    "pdf417": 2610,
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

    def to_pillow(self) -> Any:
        """Return the PNG as a Pillow Image, when Pillow is installed."""
        try:
            pillow_image: Any = import_module("PIL.Image")
        except ImportError as exc:
            raise ImportError(
                "BarcodeImage.to_pillow() requires Pillow. "
                "Install Pillow in your application to use this helper."
            ) from exc

        image = pillow_image.open(BytesIO(self.png))
        image.load()
        return image

    def to_cv2(self) -> Any:
        """Return the PNG as an OpenCV image, when OpenCV and NumPy are installed."""
        try:
            cv2: Any = import_module("cv2")
            numpy: Any = import_module("numpy")
        except ImportError as exc:
            raise ImportError(
                "BarcodeImage.to_cv2() requires OpenCV and NumPy. "
                "Install opencv-python and numpy in your application to use this helper."
            ) from exc

        data = numpy.frombuffer(self.png, dtype=numpy.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
        if image is None:
            raise ValueError("OpenCV could not decode barcodekit PNG bytes")
        return image


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
    """Generate barcode PNGs with barcode-rest."""

    def __init__(
        self,
        executable: str | Path | None = None,
        timeout: float = 10.0,
        server: bool = False,
    ) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise TypeError("timeout must be a number")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a finite number greater than zero")
        if type(server) is not bool:
            raise TypeError("server must be a boolean")
        self._executable = executable
        self.timeout = float(timeout)
        self.server = server
        self._server_process: subprocess.Popen[bytes] | None = None
        self._server_port: int | None = None
        self._server_exit_token: str | None = None

    def __enter__(self) -> BarcodeKit:
        if self.server:
            self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def start(self) -> None:
        """Start the local barcode-rest server when server mode is enabled."""
        if not self.server:
            return
        if self._server_process is not None:
            if self._server_process.poll() is None:
                return
            self._server_process = None
            self._server_port = None
            self._server_exit_token = None

        executable = resolve_binary(self._executable)
        port = _find_free_local_port()
        exit_token = _generate_exit_token()
        command = [str(executable), "-port", str(port), "-exit-token", exit_token]

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise BarcodeKitBinaryNotFound(
                f"barcode-rest executable disappeared before it could be run: {executable}"
            ) from exc
        except OSError as exc:
            raise BarcodeKitCommandError(None, command, str(exc)) from exc

        self._server_process = process
        self._server_port = port
        self._server_exit_token = exit_token
        try:
            self._wait_for_server(command)
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        """Stop a barcode-rest server started by this instance."""
        process = self._server_process
        port = self._server_port
        exit_token = self._server_exit_token
        self._server_process = None
        self._server_port = None
        self._server_exit_token = None
        if process is None or process.poll() is not None:
            return

        if port is not None and exit_token is not None:
            _request_server_exit(port, exit_token, timeout=min(self.timeout, 2.0))
            try:
                process.wait(timeout=2.0)
                return
            except subprocess.TimeoutExpired:
                pass

        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)

    def generate(self, symbology: str, text: str, **options: object) -> BarcodeImage:
        """Generate a barcode using a supported symbology."""
        if not isinstance(symbology, str):
            raise TypeError("symbology must be a string")
        if symbology not in _SUPPORTED_SYMBOLOGIES:
            raise ValueError(f"Unsupported symbology: {symbology}")

        validated_options = _validate_options(symbology, options)
        _validate_text(symbology, text, validated_options)
        if self.server:
            return self._generate_with_server(symbology, text, validated_options)
        return self._generate_with_cli(symbology, text, validated_options)

    def _generate_with_cli(
        self,
        symbology: str,
        text: str,
        validated_options: Mapping[str, object],
    ) -> BarcodeImage:
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

    def _generate_with_server(
        self,
        symbology: str,
        text: str,
        validated_options: Mapping[str, object],
    ) -> BarcodeImage:
        self.start()
        if self._server_port is None:
            raise BarcodeKitCommandError(None, ("barcode-rest", "-port"), "server did not start")

        query: dict[str, str] = {"text": text}
        for name, value in validated_options.items():
            if isinstance(value, bool):
                query[name] = "1" if value else "0"
            else:
                query[name] = str(value)

        url = f"http://{_LOCALHOST}:{self._server_port}/{symbology}?{urlencode(query)}"
        command = _server_display_command(symbology, validated_options)
        try:
            with urlopen(url, timeout=self.timeout) as response:
                data = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise BarcodeKitCommandError(exc.code, command, _redact_stderr(detail, text)) from exc
        except TimeoutError as exc:
            raise BarcodeKitTimeout(self.timeout, command) from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise BarcodeKitTimeout(self.timeout, command) from exc
            raise BarcodeKitCommandError(None, command, str(exc.reason)) from exc
        except OSError as exc:
            raise BarcodeKitCommandError(None, command, _redact_stderr(str(exc), text)) from exc

        if not _is_png(data):
            raise BarcodeKitCommandError(0, command, "barcode-rest produced invalid PNG output")
        return BarcodeImage(data)

    def _wait_for_server(self, command: list[str]) -> None:
        if self._server_process is None or self._server_port is None:
            raise BarcodeKitCommandError(None, command, "server was not initialized")

        deadline = time.monotonic() + self.timeout
        url = f"http://{_LOCALHOST}:{self._server_port}/health"
        while time.monotonic() < deadline:
            if self._server_process.poll() is not None:
                raise BarcodeKitCommandError(
                    self._server_process.returncode,
                    command,
                    "barcode-rest server exited before it became ready",
                )
            try:
                with urlopen(url, timeout=min(0.2, self.timeout)):
                    return
            except (OSError, URLError):
                time.sleep(0.05)
        raise BarcodeKitTimeout(self.timeout, command)

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


def _find_free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((_LOCALHOST, 0))
        return int(sock.getsockname()[1])


def _generate_exit_token() -> str:
    return secrets.token_hex(16)


def _request_server_exit(port: int, exit_token: str, timeout: float) -> None:
    query = urlencode({"token": exit_token})
    url = f"http://{_LOCALHOST}:{port}/exit?{query}"
    request = Request(url, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read()
    except (HTTPError, TimeoutError, URLError, OSError):
        return


def _server_display_command(symbology: str, options: Mapping[str, object]) -> tuple[str, ...]:
    command = ["barcode-rest", "server", "GET", f"/{symbology}", "--text", "<redacted>"]
    command.extend(_build_option_arguments(options))
    return tuple(command)
