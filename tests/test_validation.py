from __future__ import annotations

from collections.abc import Callable

import pytest

from barcodekit import BarcodeKit


@pytest.mark.parametrize(
    ("action", "message"),
    [
        (lambda kit: kit.datamatrix("A" * 129), "128 UTF-8 bytes"),
        (lambda kit: kit.qr("A" * 257), "256 UTF-8 bytes"),
        (lambda kit: kit.code128("é"), "ASCII"),
        (lambda kit: kit.code39("lowercase"), "fullascii"),
        (lambda kit: kit.codabar("12345"), "start and end"),
        (lambda kit: kit.itf("123"), "even number"),
        (lambda kit: kit.code25("12A"), "digits only"),
        (lambda kit: kit.ean13("123"), "12 or 13"),
        (lambda kit: kit.ean13("4901234567890"), "check digit"),
        (lambda kit: kit.ean8("55123450"), "check digit"),
    ],
)
def test_invalid_text_is_rejected_before_execution(
    action: Callable[[BarcodeKit], object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        action(BarcodeKit())


@pytest.mark.parametrize(
    "action",
    [
        lambda kit: kit.datamatrix("ABC", size=256, module=4),
        lambda kit: kit.datamatrix("ABC", size=15),
        lambda kit: kit.code128("ABC", module=1),
        lambda kit: kit.code128("ABC", height=19),
        lambda kit: kit.code128("ABC", quiet=17),
        lambda kit: kit.qr("ABC", level="X"),
        lambda kit: kit.pdf417("ABC", level=9),
        lambda kit: kit.generate("qr", "ABC", label=True),
    ],
)
def test_invalid_options_are_rejected_before_execution(
    action: Callable[[BarcodeKit], object],
) -> None:
    with pytest.raises(ValueError):
        action(BarcodeKit())


def test_boolean_is_not_accepted_as_integer() -> None:
    with pytest.raises(TypeError):
        BarcodeKit().code128("ABC", height=True)


def test_unknown_symbology_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported symbology"):
        BarcodeKit().generate("unknown", "ABC")

