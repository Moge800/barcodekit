"""Resolve the barcode-rest executable for the current platform."""

from __future__ import annotations

import os
import platform
import stat
from pathlib import Path

from ._errors import BarcodeKitBinaryNotFound, BarcodeKitUnsupportedPlatform

_BINARY_ENV = "BARCODEKIT_BINARY"
_BINARY_DIR = Path(__file__).parent / "_bin"
_MACHINE_ALIASES = {
    "amd64": "amd64",
    "x86_64": "amd64",
    "arm64": "arm64",
    "aarch64": "arm64",
}
_SUPPORTED_PLATFORMS = {
    ("windows", "amd64"): "barcode-rest.exe",
    ("linux", "amd64"): "barcode-rest",
    ("linux", "arm64"): "barcode-rest",
    ("darwin", "amd64"): "barcode-rest",
    ("darwin", "arm64"): "barcode-rest",
}


def _current_platform() -> tuple[str, str]:
    system = platform.system().lower()
    raw_machine = platform.machine().lower()
    return system, _MACHINE_ALIASES.get(raw_machine, raw_machine)


def _bundled_binary_name() -> tuple[str, str]:
    system, machine = _current_platform()
    name = _SUPPORTED_PLATFORMS.get((system, machine))
    if name is None:
        supported = ", ".join(f"{os_name}/{arch}" for os_name, arch in _SUPPORTED_PLATFORMS)
        raise BarcodeKitUnsupportedPlatform(
            f"Unsupported platform {system}/{machine}. Supported platforms: {supported}."
        )
    return system, name


def _require_file(value: str | Path, source: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_file():
        raise BarcodeKitBinaryNotFound(f"{source} does not point to a file: {path}")
    return path


def _ensure_bundled_executable(path: Path, system: str) -> None:
    if system == "windows":
        return
    mode = path.stat().st_mode
    if mode & stat.S_IXUSR:
        return
    try:
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError as exc:
        raise BarcodeKitBinaryNotFound(
            f"Bundled binary is not executable and its permissions could not be changed: {path}"
        ) from exc


def resolve_binary(executable: str | Path | None = None) -> Path:
    """Resolve an explicit, environment-provided, or bundled executable."""
    system, bundled_name = _bundled_binary_name()

    if executable is not None:
        return _require_file(executable, "The executable argument")

    environment_path = os.environ.get(_BINARY_ENV)
    if environment_path:
        return _require_file(environment_path, _BINARY_ENV)

    bundled = _BINARY_DIR / bundled_name
    if not bundled.is_file():
        raise BarcodeKitBinaryNotFound(
            f"Bundled barcode-rest binary was not found at {bundled}. "
            f"Install the platform-specific wheel, set {_BINARY_ENV}, "
            "or pass executable= to BarcodeKit."
        )
    _ensure_bundled_executable(bundled, system)
    return bundled
