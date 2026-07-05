"""Public exceptions raised by barcodekit."""

from __future__ import annotations

from collections.abc import Sequence


def _redact_command(command: Sequence[str]) -> tuple[str, ...]:
    """Return command arguments with the barcode text removed."""
    redacted = list(command)
    for index, argument in enumerate(redacted[:-1]):
        if argument == "--text":
            redacted[index + 1] = "<redacted>"
    return tuple(redacted)


def _display_command(command: Sequence[str]) -> str:
    return " ".join(_redact_command(command))


class BarcodeKitError(Exception):
    """Base class for barcodekit errors."""


class BarcodeKitBinaryNotFound(BarcodeKitError):
    """Raised when the configured or bundled executable cannot be found."""


class BarcodeKitUnsupportedPlatform(BarcodeKitError):
    """Raised when barcodekit does not support the current platform."""


class BarcodeKitCommandError(BarcodeKitError):
    """Raised when barcode-rest fails or returns unusable output."""

    def __init__(
        self,
        returncode: int | None,
        command: Sequence[str],
        stderr: str,
    ) -> None:
        self.returncode = returncode
        self.command = _redact_command(command)
        self.stderr = stderr
        code = "could not be started" if returncode is None else f"exited with code {returncode}"
        detail = stderr.strip() or "no error details"
        super().__init__(f"barcode-rest {code}: {_display_command(command)}; {detail}")


class BarcodeKitTimeout(BarcodeKitError):
    """Raised when barcode-rest does not finish before the timeout."""

    def __init__(self, timeout: float, command: Sequence[str]) -> None:
        self.timeout = timeout
        self.command = _redact_command(command)
        super().__init__(
            f"barcode-rest timed out after {timeout:g} seconds: {_display_command(command)}"
        )

