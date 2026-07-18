from __future__ import annotations

import subprocess
import time
from pathlib import Path
from threading import Event, Thread
from typing import Any

import pytest

import barcodekit
from barcodekit import BarcodeImage, BarcodeKit, BarcodeKitBatchError, _core


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


def test_generate_many_requires_server_mode() -> None:
    with pytest.raises(ValueError, match="server=True"):
        BarcodeKit().generate_many("qr", ["A"])


@pytest.mark.parametrize("workers", [0, -1])
def test_generate_many_rejects_non_positive_workers(workers: int) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        BarcodeKit(server=True).generate_many("qr", ["A"], workers=workers)


@pytest.mark.parametrize("workers", [True, 1.5, "2"])
def test_generate_many_rejects_non_integer_workers(workers: Any) -> None:
    with pytest.raises(TypeError, match="integer or None"):
        BarcodeKit(server=True).generate_many("qr", ["A"], workers=workers)


def test_generate_many_does_not_start_server_for_empty_input(monkeypatch: Any) -> None:
    kit = BarcodeKit(server=True)

    def fail_start() -> None:
        raise AssertionError("server should not start")

    monkeypatch.setattr(kit, "start", fail_start)

    assert kit.generate_many("qr", [], workers=2) == []


def test_generate_many_preserves_input_order(
    monkeypatch: Any,
    png_bytes: bytes,
) -> None:
    kit = BarcodeKit(server=True)
    monkeypatch.setattr(kit, "start", lambda: None)

    def fake_generate(
        symbology: str,
        text: str,
        options: object,
    ) -> BarcodeImage:
        time.sleep({"ITEM-0": 0.03, "ITEM-1": 0.01, "ITEM-2": 0.0}[text])
        return BarcodeImage(png_bytes + text.encode("ascii"))

    monkeypatch.setattr(kit, "_generate_batch_item", fake_generate)

    images = kit.generate_many(
        "datamatrix",
        ["ITEM-0", "ITEM-1", "ITEM-2"],
        workers=3,
        size=256,
    )

    assert [image.to_bytes().removeprefix(png_bytes) for image in images] == [
        b"ITEM-0",
        b"ITEM-1",
        b"ITEM-2",
    ]


def test_imap_bounds_input_consumption(
    monkeypatch: Any,
    png_bytes: bytes,
) -> None:
    kit = BarcodeKit(server=True)
    monkeypatch.setattr(kit, "start", lambda: None)
    monkeypatch.setattr(
        kit,
        "_generate_batch_item",
        lambda symbology, text, options: BarcodeImage(png_bytes),
    )
    consumed = 0

    def texts() -> Any:
        nonlocal consumed
        for index in range(100):
            consumed += 1
            yield f"ITEM-{index}"

    images = kit.imap("datamatrix", texts(), workers=2, size=256)

    assert consumed == 0
    next(images)
    assert consumed == 4
    images.close()


def test_generate_many_reports_failing_input_index(
    monkeypatch: Any,
    png_bytes: bytes,
) -> None:
    kit = BarcodeKit(server=True)
    monkeypatch.setattr(kit, "start", lambda: None)

    def fake_generate(
        symbology: str,
        text: str,
        options: object,
    ) -> BarcodeImage:
        if text == "bad":
            raise ValueError("invalid test value")
        return BarcodeImage(png_bytes)

    monkeypatch.setattr(kit, "_generate_batch_item", fake_generate)

    with pytest.raises(BarcodeKitBatchError) as captured:
        kit.generate_many("datamatrix", ["good", "bad", "later"], workers=2)

    assert captured.value.index == 1
    assert isinstance(captured.value.error, ValueError)
    assert "good" not in str(captured.value)
    assert "bad" not in str(captured.value)


def test_close_waits_for_active_server_request(
    monkeypatch: Any,
    png_bytes: bytes,
) -> None:
    kit = BarcodeKit(server=True)
    request_started = Event()
    allow_request_to_finish = Event()
    close_called = Event()
    close_finished = Event()
    images: list[BarcodeImage] = []

    def fake_start() -> None:
        kit._server_port = 54321

    def fake_request(
        port: int,
        symbology: str,
        text: str,
        options: object,
    ) -> BarcodeImage:
        request_started.set()
        allow_request_to_finish.wait(timeout=2)
        return BarcodeImage(png_bytes)

    def generate() -> None:
        images.append(kit.qr("ABC", size=256))

    def close() -> None:
        close_called.set()
        kit.close()
        close_finished.set()

    monkeypatch.setattr(kit, "_start_server_locked", fake_start)
    monkeypatch.setattr(kit, "_request_server_image", fake_request)
    generate_thread = Thread(target=generate)
    close_thread = Thread(target=close)

    generate_thread.start()
    assert request_started.wait(timeout=2)
    close_thread.start()
    assert close_called.wait(timeout=2)
    assert close_finished.wait(timeout=0.05) is False

    allow_request_to_finish.set()
    generate_thread.join(timeout=2)
    close_thread.join(timeout=2)

    assert images == [BarcodeImage(png_bytes)]
    assert close_finished.is_set()


def test_local_http_opener_disables_environment_proxies() -> None:
    assert _core._LOCAL_PROXY_HANDLER.proxies == {}


def test_server_start_cleans_up_after_keyboard_interrupt(monkeypatch: Any) -> None:
    monkeypatch.setattr(_core, "resolve_binary", lambda executable: Path("barcode-rest"))
    monkeypatch.setattr(_core, "_find_free_local_port", lambda: 54321)
    monkeypatch.setattr(_core, "_generate_exit_token", lambda: "exit-token")
    exit_requests: list[tuple[int, str]] = []

    class FakeProcess:
        returncode = None
        waited = False

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            self.waited = True
            self.returncode = 0
            return 0

        def kill(self) -> None:
            self.returncode = -9

    process = FakeProcess()

    def interrupt_startup(self: BarcodeKit, command: list[str]) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(subprocess, "Popen", lambda command, **kwargs: process)
    monkeypatch.setattr(BarcodeKit, "_wait_for_server", interrupt_startup)
    monkeypatch.setattr(
        _core,
        "_request_server_exit",
        lambda port, token, timeout: exit_requests.append((port, token)),
    )

    kit = BarcodeKit(server=True)
    try:
        kit.start()
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("KeyboardInterrupt should be re-raised")

    assert exit_requests == [(54321, "exit-token")]
    assert process.waited is True
    assert kit._server_process is None
    assert kit._server_port is None
    assert kit._server_exit_token is None


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
    monkeypatch.setattr(_core, "_open_local", fake_urlopen)

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
    monkeypatch.setattr(_core, "_open_local", lambda request, timeout: FakeResponse())

    kit = BarcodeKit(server=True)
    kit.start()
    processes[0].returncode = 1
    kit.start()
    kit.close()

    assert captured_commands == [
        ["barcode-rest", "-port", "54321", "-exit-token", "first-token"],
        ["barcode-rest", "-port", "54322", "-exit-token", "second-token"],
    ]
