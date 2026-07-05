from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from barcodekit import BarcodeKit, _core


def _mock_success(
    monkeypatch: Any,
    png_bytes: bytes,
    captured: dict[str, Any],
) -> None:
    monkeypatch.setattr(_core, "resolve_binary", lambda executable: Path("barcode-rest"))

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, png_bytes, b"")

    monkeypatch.setattr(subprocess, "run", fake_run)


def test_command_uses_generate_text_and_stdout(
    monkeypatch: Any, png_bytes: bytes
) -> None:
    captured: dict[str, Any] = {}
    _mock_success(monkeypatch, png_bytes, captured)

    BarcodeKit().datamatrix("ABC123", size=256, quiet=4)

    assert captured["command"] == [
        "barcode-rest",
        "generate",
        "datamatrix",
        "--text",
        "ABC123",
        "--output",
        "-",
        "--size",
        "256",
        "--quiet",
        "4",
    ]
    assert captured["kwargs"] == {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "timeout": 10.0,
        "check": False,
        "shell": False,
    }


def test_boolean_flags_are_only_included_when_true(
    monkeypatch: Any, png_bytes: bytes
) -> None:
    captured: dict[str, Any] = {}
    _mock_success(monkeypatch, png_bytes, captured)

    BarcodeKit().code39("lowercase", label=False, fullascii=True)

    command = captured["command"]
    assert "--label" not in command
    assert "--fullascii" in command


def test_none_options_are_omitted(monkeypatch: Any, png_bytes: bytes) -> None:
    captured: dict[str, Any] = {}
    _mock_success(monkeypatch, png_bytes, captured)

    BarcodeKit().code128("ABC123", module=None, height=None, quiet=None)

    assert captured["command"][-2:] == ["--output", "-"]


def test_underscores_become_hyphenated_flags() -> None:
    assert _core._option_flag("future_option") == "--future-option"


def test_qr_level_is_normalized(monkeypatch: Any, png_bytes: bytes) -> None:
    captured: dict[str, Any] = {}
    _mock_success(monkeypatch, png_bytes, captured)

    BarcodeKit().qr("ABC123", level="q")

    assert captured["command"][-2:] == ["--level", "Q"]
