"""Synchronize package metadata from a GitHub release tag."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_VERSION_PATTERN = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")
_VERSION_LINK_PATTERN = re.compile(
    r"https://github\.com/Moge800/barcodekit/blob/"
    r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)/"
    r"THIRD_PARTY_NOTICES\.md"
)


def _version_from_tag(tag: str) -> str:
    if not tag.startswith("v"):
        raise ValueError(f"Release tag must be v<major>.<minor>.<patch>, got {tag!r}")
    version = tag.removeprefix("v")
    if _VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError(f"Release tag must be v<major>.<minor>.<patch>, got {tag!r}")
    return version


def _update_project_version(path: Path, version: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    section = ""
    replacements = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped
        elif section == "[project]" and re.match(r"^version\s*=", stripped):
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f'version = "{version}"{newline}'
            replacements += 1
    if replacements != 1:
        raise ValueError(f"Expected one [project] version in {path}, found {replacements}")
    path.write_text("".join(lines), encoding="utf-8")


def _replace_once(path: Path, pattern: re.Pattern[str], replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = pattern.subn(replacement, text)
    if count != 1:
        raise ValueError(f"Expected one version marker in {path}, found {count}")
    path.write_text(updated, encoding="utf-8")


def sync_release_version(root: Path, tag: str) -> str:
    """Update all package-version markers from a release tag."""
    version = _version_from_tag(tag)
    _update_project_version(root / "pyproject.toml", version)
    _replace_once(
        root / "src" / "barcodekit" / "_version.py",
        re.compile(r'(?m)^__version__\s*=\s*"[^"]+"$'),
        f'__version__ = "{version}"',
    )
    notice_url = (
        f"https://github.com/Moge800/barcodekit/blob/v{version}/THIRD_PARTY_NOTICES.md"
    )
    _replace_once(root / "README.md", _VERSION_LINK_PATTERN, notice_url)
    _replace_once(root / "README_JP.md", _VERSION_LINK_PATTERN, notice_url)
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="release tag, for example v0.1.0")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="project root",
    )
    arguments = parser.parse_args()

    version = sync_release_version(arguments.root, arguments.tag)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
