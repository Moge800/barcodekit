"""Prepare one barcode-rest executable for a platform-specific wheel."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import stat
import subprocess
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_BINARY_DIR = _PROJECT_ROOT / "src" / "barcodekit" / "_bin"
_TARGET_FILENAMES = {
    "windows-amd64": "barcode-rest.exe",
    "linux-amd64": "barcode-rest",
    "linux-arm64": "barcode-rest",
    "darwin-amd64": "barcode-rest",
    "darwin-arm64": "barcode-rest",
}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_png(data: bytes) -> bool:
    return (
        len(data) >= 45
        and data.startswith(_PNG_SIGNATURE)
        and data[12:16] == b"IHDR"
        and data[-12:-8] == b"\x00\x00\x00\x00"
        and data[-8:-4] == b"IEND"
    )


def verify_binary(source: Path, expected_version: str, timeout: float = 10.0) -> None:
    """Verify a native binary's version and one-shot PNG generation."""
    try:
        version_result = subprocess.run(  # noqa: UP022 - explicit PIPEs aid review
            [str(source), "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Could not execute {source} for version verification") from exc

    version_output = version_result.stdout.decode("utf-8", errors="replace").strip()
    if version_result.returncode != 0:
        stderr = version_result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(
            f"{source} -version failed with code {version_result.returncode}: {stderr}"
        )
    if expected_version not in version_output.split():
        raise ValueError(
            f"Version mismatch for {source}: expected token {expected_version!r}, "
            f"got {version_output!r}"
        )

    command = [
        str(source),
        "generate",
        "datamatrix",
        "--text",
        "BARCODEKIT-BUILD-CHECK",
        "--output",
        "-",
        "--size",
        "256",
    ]
    try:
        image_result = subprocess.run(  # noqa: UP022 - explicit PIPEs aid review
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Could not execute {source} for PNG verification") from exc

    if image_result.returncode != 0:
        stderr = image_result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(
            f"Data Matrix smoke test failed with code {image_result.returncode}: {stderr}"
        )
    if not _is_png(image_result.stdout):
        raise ValueError("Data Matrix smoke test did not return a valid PNG")


def prepare_binary(
    source: Path,
    target: str,
    *,
    expected_sha256: str | None = None,
    expected_version: str | None = None,
    destination_dir: Path = _BINARY_DIR,
) -> Path:
    """Copy and permission a binary for one target platform."""
    if target not in _TARGET_FILENAMES:
        choices = ", ".join(_TARGET_FILENAMES)
        raise ValueError(f"Unknown target {target!r}. Expected one of: {choices}")
    if not source.is_file():
        raise FileNotFoundError(f"Binary does not exist: {source}")

    actual_sha256 = _sha256(source)
    if expected_sha256 is not None and actual_sha256 != expected_sha256.lower():
        raise ValueError(
            f"SHA-256 mismatch for {source}: expected {expected_sha256.lower()}, "
            f"got {actual_sha256}"
        )
    destination_dir.mkdir(parents=True, exist_ok=True)
    filename = _TARGET_FILENAMES[target]
    destination = destination_dir / filename

    other_filename = "barcode-rest" if filename.endswith(".exe") else "barcode-rest.exe"
    other_binary = destination_dir / other_filename
    if other_binary.is_file():
        other_binary.unlink()

    shutil.copy2(source, destination)
    if target != "windows-amd64":
        mode = destination.stat().st_mode
        destination.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if expected_version is not None:
        try:
            verify_binary(destination, expected_version)
        except ValueError:
            destination.unlink(missing_ok=True)
            raise
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path, help="barcode-rest binary to copy")
    parser.add_argument("--target", required=True, choices=tuple(_TARGET_FILENAMES))
    parser.add_argument(
        "--sha256",
        dest="expected_sha256",
        help="expected SHA-256 digest; the copy is rejected if it does not match",
    )
    parser.add_argument(
        "--expected-version",
        help="expected version token; also enables a native PNG smoke test",
    )
    arguments = parser.parse_args()

    try:
        destination = prepare_binary(
            arguments.binary,
            arguments.target,
            expected_sha256=arguments.expected_sha256,
            expected_version=arguments.expected_version,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
