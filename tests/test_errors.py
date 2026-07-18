from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from barcodekit import BarcodeKit, BarcodeKitCommandError, BarcodeKitTimeout, _core, _errors


def _mock_binary(monkeypatch: Any) -> None:
    monkeypatch.setattr(_core, "resolve_binary", lambda executable: Path("barcode-rest"))


def test_nonzero_exit_raises_command_error_and_redacts_text(monkeypatch: Any) -> None:
    _mock_binary(monkeypatch)
    secret = "CUSTOMER-SECRET"

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            command,
            2,
            b"",
            f"cannot encode {secret}".encode(),
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(BarcodeKitCommandError) as caught:
        BarcodeKit().code128(secret)

    error = caught.value
    assert error.returncode == 2
    assert secret not in str(error)
    assert secret not in repr(error)
    assert secret not in error.command
    assert "<redacted>" in str(error)


def test_timeout_raises_redacted_timeout(monkeypatch: Any) -> None:
    _mock_binary(monkeypatch)
    secret = "CUSTOMER-SECRET"

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(command, 0.25)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(BarcodeKitTimeout) as caught:
        BarcodeKit(timeout=0.25).code128(secret)

    assert secret not in str(caught.value)
    assert "<redacted>" in str(caught.value)


def test_invalid_png_raises_command_error(monkeypatch: Any) -> None:
    _mock_binary(monkeypatch)

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(command, 0, b"not a png", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(BarcodeKitCommandError, match="invalid PNG"):
        BarcodeKit().datamatrix("ABC123")


def test_stderr_decoding_replaces_invalid_utf8(monkeypatch: Any) -> None:
    _mock_binary(monkeypatch)

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(command, 1, b"", b"\xff")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(BarcodeKitCommandError) as caught:
        BarcodeKit().datamatrix("ABC123")

    assert "\ufffd" in str(caught.value)


def test_command_display_preserves_argument_boundaries_and_redacts_text() -> None:
    secret = "CUSTOMER SECRET"

    display = _errors._display_command(
        [
            "C:/Program Files/barcode-rest.exe",
            "generate",
            "code128",
            "--text",
            secret,
            "--output",
            "-",
        ]
    )

    assert secret not in display
    assert "<redacted>" in display
    assert (
        '"C:/Program Files/barcode-rest.exe"' in display
        or "'C:/Program Files/barcode-rest.exe'" in display
    )


def test_command_display_redacts_exit_token() -> None:
    secret = "server-exit-token"

    display = _errors._display_command(
        [
            "barcode-rest",
            "-port",
            "54321",
            "-exit-token",
            secret,
        ]
    )

    assert secret not in display
    assert "<redacted>" in display
