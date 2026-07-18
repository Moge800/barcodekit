from __future__ import annotations

import hashlib
import importlib.util
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest

_SCRIPT = Path(__file__).parents[1] / "scripts" / "prepare_binary.py"
_SPEC = importlib.util.spec_from_file_location("prepare_binary", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE: Any = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
prepare_binary = _MODULE.prepare_binary


def test_prepare_windows_binary_removes_linux_binary(tmp_path: Path) -> None:
    source = tmp_path / "source.exe"
    destination_dir = tmp_path / "package"
    source.write_bytes(b"windows")
    destination_dir.mkdir()
    (destination_dir / "barcode-rest").write_bytes(b"stale")

    result = prepare_binary(source, "windows-amd64", destination_dir=destination_dir)

    assert result == destination_dir / "barcode-rest.exe"
    assert result.read_bytes() == b"windows"
    assert not (destination_dir / "barcode-rest").exists()


def test_prepare_binary_checks_sha256(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"linux")
    digest = hashlib.sha256(b"linux").hexdigest()

    result = prepare_binary(
        source,
        "linux-amd64",
        expected_sha256=digest,
        destination_dir=tmp_path / "package",
    )

    assert result.read_bytes() == b"linux"
    if os.name != "nt":
        assert result.stat().st_mode & stat.S_IXUSR


@pytest.mark.parametrize("target", ["darwin-amd64", "darwin-arm64"])
def test_prepare_macos_binary(target: str, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"macos")

    result = prepare_binary(source, target, destination_dir=tmp_path / "package")

    assert result == tmp_path / "package" / "barcode-rest"
    assert result.read_bytes() == b"macos"
    if os.name != "nt":
        assert result.stat().st_mode & stat.S_IXUSR


def test_prepare_binary_rejects_wrong_sha256(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"binary")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        prepare_binary(
            source,
            "linux-arm64",
            expected_sha256="0" * 64,
            destination_dir=tmp_path / "package",
        )


def test_verify_binary_checks_version_and_png(
    monkeypatch: Any,
    tmp_path: Path,
    png_bytes: bytes,
) -> None:
    source = tmp_path / "barcode-rest"
    source.write_bytes(b"binary")
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(command)
        if command[-1] == "-version":
            return subprocess.CompletedProcess(command, 0, b"barcode-rest v0.1.0\n", b"")
        return subprocess.CompletedProcess(command, 0, png_bytes, b"")

    monkeypatch.setattr(_MODULE.subprocess, "run", fake_run)

    _MODULE.verify_binary(source, "v0.1.0")

    assert calls[0] == [str(source), "-version"]
    assert calls[1][1:3] == ["generate", "datamatrix"]


def test_prepare_verifies_copied_binary(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    source = tmp_path / "download" / "barcode-rest-linux-amd64"
    source.parent.mkdir()
    source.write_bytes(b"binary")
    destination_dir = tmp_path / "package"
    verified: list[Path] = []

    def fake_verify(binary: Path, version: str, timeout: float = 10.0) -> None:
        assert version == "v0.3.0"
        verified.append(binary)

    monkeypatch.setattr(_MODULE, "verify_binary", fake_verify)

    result = prepare_binary(
        source,
        "linux-amd64",
        expected_version="v0.3.0",
        destination_dir=destination_dir,
    )

    assert verified == [result]
    assert result == destination_dir / "barcode-rest"


def test_failed_verification_removes_copied_binary(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    source = tmp_path / "barcode-rest-linux-amd64"
    source.write_bytes(b"binary")
    destination_dir = tmp_path / "package"

    def fake_verify(binary: Path, version: str, timeout: float = 10.0) -> None:
        raise ValueError("wrong binary")

    monkeypatch.setattr(_MODULE, "verify_binary", fake_verify)

    with pytest.raises(ValueError, match="wrong binary"):
        prepare_binary(
            source,
            "linux-amd64",
            expected_version="v0.3.0",
            destination_dir=destination_dir,
        )

    assert not (destination_dir / "barcode-rest").exists()
