"""Verify a barcodekit platform wheel before it is retained or published."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

_TARGETS = {
    "windows-amd64": ("barcodekit/_bin/barcode-rest.exe", "win_amd64"),
    "linux-amd64": ("barcodekit/_bin/barcode-rest", "manylinux_2_34_x86_64"),
    "linux-arm64": ("barcodekit/_bin/barcode-rest", "manylinux_2_17_aarch64"),
    "darwin-amd64": ("barcodekit/_bin/barcode-rest", "macosx_12_0_x86_64"),
    "darwin-arm64": ("barcodekit/_bin/barcode-rest", "macosx_12_0_arm64"),
}
_REQUIRED_LICENSE_PATHS = {
    "LICENSE",
    "NOTICE",
    "THIRD_PARTY_NOTICES.md",
    "licenses/boombuler-barcode-MIT.txt",
    "licenses/go-and-x-image-BSD-3-Clause.txt",
}


def _single_wheel(wheel_dir: Path) -> Path:
    wheels = sorted(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError(f"Expected exactly one wheel in {wheel_dir}, found {len(wheels)}")
    return wheels[0]


def verify_wheel(wheel: Path, target: str) -> None:
    """Verify binary selection, platform tag, typing marker, and license files."""
    if target not in _TARGETS:
        choices = ", ".join(_TARGETS)
        raise ValueError(f"Unknown target {target!r}. Expected one of: {choices}")
    if not wheel.is_file():
        raise FileNotFoundError(f"Wheel does not exist: {wheel}")

    expected_binary, platform_tag = _TARGETS[target]
    if not wheel.name.endswith(f"-{platform_tag}.whl"):
        raise ValueError(f"Wheel filename does not have platform tag {platform_tag}: {wheel.name}")

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        binaries = sorted(
            name
            for name in names
            if name.startswith("barcodekit/_bin/barcode-rest")
        )
        if binaries != [expected_binary]:
            raise ValueError(
                f"Wheel must contain only {expected_binary}; found: {binaries or 'none'}"
            )
        if archive.getinfo(expected_binary).file_size == 0:
            raise ValueError(f"Bundled binary is empty: {expected_binary}")
        if "barcodekit/py.typed" not in names:
            raise ValueError("Wheel does not contain barcodekit/py.typed")

        wheel_metadata = [name for name in names if name.endswith(".dist-info/WHEEL")]
        if len(wheel_metadata) != 1:
            raise ValueError("Wheel must contain exactly one .dist-info/WHEEL file")
        metadata = archive.read(wheel_metadata[0]).decode("utf-8")
        expected_tag = f"Tag: py3-none-{platform_tag}"
        if expected_tag not in metadata.splitlines():
            raise ValueError(f"WHEEL metadata does not contain {expected_tag}")

        dist_info_dir = wheel_metadata[0].removesuffix("/WHEEL")
        license_root = f"{dist_info_dir}/licenses/"
        included_license_paths = {
            name.removeprefix(license_root)
            for name in names
            if name.startswith(license_root)
        }
        missing_licenses = _REQUIRED_LICENSE_PATHS - included_license_paths
        if missing_licenses:
            missing = ", ".join(sorted(missing_licenses))
            raise ValueError(f"Wheel is missing required license files: {missing}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument("--wheel", type=Path)
    location.add_argument("--wheel-dir", type=Path)
    parser.add_argument("--target", required=True, choices=tuple(_TARGETS))
    arguments = parser.parse_args()

    wheel = arguments.wheel or _single_wheel(arguments.wheel_dir)
    verify_wheel(wheel, arguments.target)
    print(wheel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
