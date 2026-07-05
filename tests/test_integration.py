from __future__ import annotations

import os

import pytest

from barcodekit import BarcodeKit


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("BARCODEKIT_BINARY"),
    reason="BARCODEKIT_BINARY is not set",
)
def test_real_binary_generates_datamatrix_png() -> None:
    image = BarcodeKit().datamatrix("ABC123", size=256)

    assert image.to_bytes().startswith(b"\x89PNG\r\n\x1a\n")

