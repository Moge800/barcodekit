from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_SCRIPT = Path(__file__).parents[1] / "scripts" / "sync_release_version.py"
_SPEC = importlib.util.spec_from_file_location("sync_release_version", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE: Any = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
sync_release_version = _MODULE.sync_release_version


def _write_project(root: Path) -> None:
    (root / "src" / "barcodekit").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["hatchling"]\n\n'
        '[project]\nname = "barcodekit"\nversion = "0.0.1"\n',
        encoding="utf-8",
    )
    (root / "src" / "barcodekit" / "_version.py").write_text(
        '__version__ = "0.0.1"\n',
        encoding="utf-8",
    )
    notice_link = (
        "https://github.com/Moge800/barcodekit/blob/"
        "v0.0.1/THIRD_PARTY_NOTICES.md"
    )
    (root / "README.md").write_text(notice_link, encoding="utf-8")
    (root / "README_JP.md").write_text(notice_link, encoding="utf-8")


def test_sync_release_version_updates_all_markers(tmp_path: Path) -> None:
    _write_project(tmp_path)

    version = sync_release_version(tmp_path, "v0.1.0")

    assert version == "0.1.0"
    assert 'version = "0.1.0"' in (tmp_path / "pyproject.toml").read_text("utf-8")
    assert '__version__ = "0.1.0"' in (
        tmp_path / "src" / "barcodekit" / "_version.py"
    ).read_text("utf-8")
    assert "/blob/v0.1.0/THIRD_PARTY_NOTICES.md" in (
        tmp_path / "README.md"
    ).read_text("utf-8")
    assert "/blob/v0.1.0/THIRD_PARTY_NOTICES.md" in (
        tmp_path / "README_JP.md"
    ).read_text("utf-8")


@pytest.mark.parametrize("tag", ["0.1.0", "v1", "release-1.0.0", "v01.0.0"])
def test_sync_release_version_rejects_invalid_tags(tmp_path: Path, tag: str) -> None:
    _write_project(tmp_path)

    with pytest.raises(ValueError, match="Release tag must be"):
        sync_release_version(tmp_path, tag)
