from __future__ import annotations

import pytest


@pytest.fixture
def png_bytes() -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = b"\x00\x00\x00\rIHDR" + (b"\x00" * 13) + (b"\x00" * 4)
    iend = b"\x00\x00\x00\x00IEND" + (b"\x00" * 4)
    return signature + ihdr + iend

