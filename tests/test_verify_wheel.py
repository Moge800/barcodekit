from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path
from typing import Any

import pytest

_SCRIPT = Path(__file__).parents[1] / "scripts" / "verify_wheel.py"
_SPEC = importlib.util.spec_from_file_location("verify_wheel", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE: Any = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
verify_wheel = _MODULE.verify_wheel

_LICENSES = (
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "barcode-rest-MIT.txt",
    "boombuler-barcode-MIT.txt",
    "go-and-x-image-BSD-3-Clause.txt",
)


def _write_wheel(
    wheel: Path,
    *,
    binary: str = "barcodekit/_bin/barcode-rest.exe",
    tag: str = "win_amd64",
    extra_binary: str | None = None,
) -> None:
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(binary, b"binary")
        if extra_binary is not None:
            archive.writestr(extra_binary, b"wrong binary")
        archive.writestr("barcodekit/py.typed", b"")
        archive.writestr(
            "barcodekit-0.0.1.dist-info/WHEEL",
            f"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-{tag}\n",
        )
        for name in _LICENSES:
            archive.writestr(f"barcodekit-0.0.1.dist-info/licenses/{name}", b"license")


def test_verify_wheel_accepts_one_matching_binary_and_licenses(tmp_path: Path) -> None:
    wheel = tmp_path / "barcodekit-0.0.1-py3-none-win_amd64.whl"
    _write_wheel(wheel)

    verify_wheel(wheel, "windows-amd64")


def test_verify_wheel_rejects_binary_for_another_platform(tmp_path: Path) -> None:
    wheel = tmp_path / "barcodekit-0.0.1-py3-none-win_amd64.whl"
    _write_wheel(
        wheel,
        extra_binary="barcodekit/_bin/barcode-rest",
    )

    with pytest.raises(ValueError, match="must contain only"):
        verify_wheel(wheel, "windows-amd64")


def test_verify_wheel_rejects_wrong_platform_tag(tmp_path: Path) -> None:
    wheel = tmp_path / "barcodekit-0.0.1-py3-none-manylinux_2_34_x86_64.whl"
    _write_wheel(wheel, tag="manylinux_2_34_x86_64")

    with pytest.raises(ValueError, match="platform tag win_amd64"):
        verify_wheel(wheel, "windows-amd64")
