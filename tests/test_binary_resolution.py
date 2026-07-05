from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

import pytest

from barcodekit import BarcodeKitBinaryNotFound, BarcodeKitUnsupportedPlatform, _binary


def test_explicit_binary_has_priority(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    explicit = tmp_path / "explicit.exe"
    environment = tmp_path / "environment.exe"
    explicit.write_bytes(b"explicit")
    environment.write_bytes(b"environment")
    monkeypatch.setattr(_binary, "_current_platform", lambda: ("windows", "amd64"))
    monkeypatch.setenv("BARCODEKIT_BINARY", str(environment))

    assert _binary.resolve_binary(explicit) == explicit


def test_environment_binary_is_used(monkeypatch: Any, tmp_path: Path) -> None:
    environment = tmp_path / "barcode-rest"
    environment.write_bytes(b"binary")
    monkeypatch.setattr(_binary, "_current_platform", lambda: ("linux", "amd64"))
    monkeypatch.setenv("BARCODEKIT_BINARY", str(environment))

    assert _binary.resolve_binary() == environment


def test_missing_explicit_binary_raises(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(_binary, "_current_platform", lambda: ("windows", "amd64"))

    with pytest.raises(BarcodeKitBinaryNotFound):
        _binary.resolve_binary(tmp_path / "missing.exe")


def test_missing_bundled_binary_raises(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(_binary, "_current_platform", lambda: ("linux", "amd64"))
    monkeypatch.setattr(_binary, "_BINARY_DIR", tmp_path)
    monkeypatch.delenv("BARCODEKIT_BINARY", raising=False)

    with pytest.raises(BarcodeKitBinaryNotFound):
        _binary.resolve_binary()


def test_unsupported_platform_rejects_even_explicit_binary(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    binary = tmp_path / "barcode-rest"
    binary.write_bytes(b"binary")
    monkeypatch.setattr(_binary, "_current_platform", lambda: ("darwin", "arm64"))

    with pytest.raises(BarcodeKitUnsupportedPlatform):
        _binary.resolve_binary(binary)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are required")
def test_bundled_linux_binary_gets_execute_bits(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    binary = tmp_path / "barcode-rest"
    binary.write_bytes(b"binary")
    binary.chmod(stat.S_IRUSR | stat.S_IWUSR)
    monkeypatch.setattr(_binary, "_current_platform", lambda: ("linux", "arm64"))
    monkeypatch.setattr(_binary, "_BINARY_DIR", tmp_path)
    monkeypatch.delenv("BARCODEKIT_BINARY", raising=False)

    assert _binary.resolve_binary() == binary
    assert binary.stat().st_mode & stat.S_IXUSR
