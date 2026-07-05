from __future__ import annotations

from pathlib import Path
from typing import Any

import barcodekit
from barcodekit import BarcodeImage, BarcodeKit


def test_barcode_image_to_bytes(png_bytes: bytes) -> None:
    image = BarcodeImage(png_bytes)

    assert image.to_bytes() == png_bytes


def test_barcode_image_save(tmp_path: Path, png_bytes: bytes) -> None:
    image = BarcodeImage(png_bytes)
    destination = tmp_path / "nested-name.png"

    result = image.save(destination)

    assert result == destination
    assert destination.read_bytes() == png_bytes


def test_module_function_uses_default_engine(monkeypatch: Any, png_bytes: bytes) -> None:
    expected = BarcodeImage(png_bytes)

    class FakeKit:
        def datamatrix(
            self,
            text: str,
            *,
            size: int | None,
            module: int | None,
            quiet: int | None,
        ) -> BarcodeImage:
            assert (text, size, module, quiet) == ("ABC123", 300, None, 4)
            return expected

    monkeypatch.setattr(barcodekit, "_default_kit", FakeKit())

    assert barcodekit.datamatrix("ABC123", size=300, quiet=4) is expected


def test_timeout_must_be_positive_and_finite() -> None:
    for value in (0, -1, float("inf"), float("nan")):
        try:
            BarcodeKit(timeout=value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{value!r} should have been rejected")

