from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import barcodekit
from barcodekit import BarcodeImage, BarcodeKit, _core


def test_barcode_image_to_bytes(png_bytes: bytes) -> None:
    image = BarcodeImage(png_bytes)

    assert image.to_bytes() == png_bytes


def test_barcode_image_save(tmp_path: Path, png_bytes: bytes) -> None:
    image = BarcodeImage(png_bytes)
    destination = tmp_path / "nested-name.png"

    result = image.save(destination)

    assert result == destination
    assert destination.read_bytes() == png_bytes


def test_barcode_image_to_pillow_uses_optional_pillow(
    monkeypatch: Any,
    png_bytes: bytes,
) -> None:
    opened: list[bytes] = []

    class FakePillowImage:
        loaded = False

        def load(self) -> None:
            self.loaded = True

    pillow_image = FakePillowImage()

    class FakePillowModule:
        @staticmethod
        def open(stream: Any) -> FakePillowImage:
            opened.append(stream.read())
            return pillow_image

    def fake_import_module(name: str) -> object:
        if name == "PIL.Image":
            return FakePillowModule
        raise ImportError(name)

    monkeypatch.setattr(_core, "import_module", fake_import_module)

    result = BarcodeImage(png_bytes).to_pillow()

    assert result is pillow_image
    assert opened == [png_bytes]
    assert pillow_image.loaded is True


def test_barcode_image_to_pillow_requires_pillow(
    monkeypatch: Any,
    png_bytes: bytes,
) -> None:
    def fake_import_module(name: str) -> object:
        raise ImportError(name)

    monkeypatch.setattr(_core, "import_module", fake_import_module)

    try:
        BarcodeImage(png_bytes).to_pillow()
    except ImportError as exc:
        assert "requires Pillow" in str(exc)
    else:
        raise AssertionError("to_pillow() should require Pillow")


def test_barcode_image_to_cv2_uses_optional_cv2_and_numpy(
    monkeypatch: Any,
    png_bytes: bytes,
) -> None:
    cv_image = object()
    decoded: list[tuple[object, object]] = []

    class FakeNumpyModule:
        uint8 = object()

        @staticmethod
        def frombuffer(data: bytes, *, dtype: object) -> object:
            assert data == png_bytes
            assert dtype is FakeNumpyModule.uint8
            return ("array", data)

    class FakeCv2Module:
        IMREAD_UNCHANGED = object()

        @staticmethod
        def imdecode(data: object, flags: object) -> object:
            decoded.append((data, flags))
            return cv_image

    def fake_import_module(name: str) -> object:
        if name == "cv2":
            return FakeCv2Module
        if name == "numpy":
            return FakeNumpyModule
        raise ImportError(name)

    monkeypatch.setattr(_core, "import_module", fake_import_module)

    result = BarcodeImage(png_bytes).to_cv2()

    assert result is cv_image
    assert decoded == [(("array", png_bytes), FakeCv2Module.IMREAD_UNCHANGED)]


def test_barcode_image_to_cv2_requires_cv2_and_numpy(
    monkeypatch: Any,
    png_bytes: bytes,
) -> None:
    def fake_import_module(name: str) -> object:
        raise ImportError(name)

    monkeypatch.setattr(_core, "import_module", fake_import_module)

    try:
        BarcodeImage(png_bytes).to_cv2()
    except ImportError as exc:
        assert "requires OpenCV and NumPy" in str(exc)
    else:
        raise AssertionError("to_cv2() should require OpenCV and NumPy")


def test_barcode_image_to_cv2_rejects_decode_failure(
    monkeypatch: Any,
    png_bytes: bytes,
) -> None:
    class FakeNumpyModule:
        uint8 = object()

        @staticmethod
        def frombuffer(data: bytes, *, dtype: object) -> object:
            return data

    class FakeCv2Module:
        IMREAD_UNCHANGED = object()

        @staticmethod
        def imdecode(data: object, flags: object) -> None:
            return None

    def fake_import_module(name: str) -> object:
        if name == "cv2":
            return FakeCv2Module
        if name == "numpy":
            return FakeNumpyModule
        raise ImportError(name)

    monkeypatch.setattr(_core, "import_module", fake_import_module)

    try:
        BarcodeImage(png_bytes).to_cv2()
    except ValueError as exc:
        assert "could not decode" in str(exc)
    else:
        raise AssertionError("to_cv2() should reject decode failure")


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


def test_server_must_be_boolean() -> None:
    try:
        BarcodeKit(server=1)  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("server=1 should have been rejected")


def test_barcodekit_factory_returns_engine() -> None:
    kit = barcodekit.barcodekit(server=True, timeout=2)

    assert isinstance(kit, BarcodeKit)
    assert kit.server is True
    assert kit.timeout == 2


def test_server_mode_starts_local_server_and_closes(
    monkeypatch: Any,
    png_bytes: bytes,
) -> None:
    monkeypatch.setattr(_core, "resolve_binary", lambda executable: Path("barcode-rest"))
    monkeypatch.setattr(_core, "_find_free_local_port", lambda: 54321)
    monkeypatch.setattr(_core, "_generate_exit_token", lambda: "exit-token")
    captured_commands: list[list[str]] = []
    requested_requests: list[tuple[str, str]] = []

    class FakeProcess:
        returncode = None
        terminated = False
        killed = False

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def kill(self) -> None:
            self.killed = True

    process = FakeProcess()

    def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
        captured_commands.append(command)
        assert kwargs == {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "shell": False,
        }
        return process

    class FakeResponse:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return self._body

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        url = request.full_url if hasattr(request, "full_url") else request
        method = request.get_method() if hasattr(request, "get_method") else "GET"
        requested_requests.append((method, url))
        if url.endswith("/health"):
            return FakeResponse(b'{"ok":true}')
        return FakeResponse(png_bytes)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(_core, "urlopen", fake_urlopen)

    with BarcodeKit(server=True, timeout=3) as kit:
        image = kit.qr("ABC 123", size=256, level="H")

    assert image.to_bytes() == png_bytes
    assert captured_commands == [
        ["barcode-rest", "-port", "54321", "-exit-token", "exit-token"]
    ]
    assert requested_requests == [
        ("GET", "http://127.0.0.1:54321/health"),
        ("GET", "http://127.0.0.1:54321/qr?text=ABC+123&size=256&level=H"),
        ("POST", "http://127.0.0.1:54321/exit?token=exit-token"),
    ]
    assert process.terminated is False
    assert process.killed is False


def test_server_mode_restarts_an_exited_process(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(_core, "resolve_binary", lambda executable: Path("barcode-rest"))
    ports = iter((54321, 54322))
    tokens = iter(("first-token", "second-token"))
    monkeypatch.setattr(_core, "_find_free_local_port", lambda: next(ports))
    monkeypatch.setattr(_core, "_generate_exit_token", lambda: next(tokens))
    captured_commands: list[list[str]] = []

    class FakeProcess:
        def __init__(self) -> None:
            self.returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            self.returncode = 0
            return 0

        def kill(self) -> None:
            self.returncode = -9

    processes = [FakeProcess(), FakeProcess()]

    def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
        captured_commands.append(command)
        return processes[len(captured_commands) - 1]

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"ok":true}'

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(_core, "urlopen", lambda request, timeout: FakeResponse())

    kit = BarcodeKit(server=True)
    kit.start()
    processes[0].returncode = 1
    kit.start()
    kit.close()

    assert captured_commands == [
        ["barcode-rest", "-port", "54321", "-exit-token", "first-token"],
        ["barcode-rest", "-port", "54322", "-exit-token", "second-token"],
    ]
