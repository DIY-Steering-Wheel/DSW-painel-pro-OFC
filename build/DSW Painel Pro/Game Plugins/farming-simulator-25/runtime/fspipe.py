from __future__ import annotations

import ctypes
import re
import threading
import time
from ctypes import wintypes
from typing import Any


INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
ERROR_PIPE_CONNECTED = 535
ERROR_PIPE_BUSY = 231
ERROR_MORE_DATA = 234
BUFFER_SIZE = 4096
MAX_INSTANCES = 10
PIPE_ACCESS_INBOUND = 0x00000001
PIPE_TYPE_MESSAGE = 0x00000004
PIPE_READMODE_MESSAGE = 0x00000002
PIPE_WAIT = 0x00000000


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_lock = threading.Lock()
_stop_event = threading.Event()
_worker_thread: threading.Thread | None = None
_pipe_name = r"\\.\pipe\fssimx"
_telemetry: dict[str, Any] = {"connected": False}
_telemetry_indexes: dict[int, str] = {}
_current_handle = None


def _default_data() -> dict[str, Any]:
    return {"connected": False}


def configure(pipe_name: str = "fssimx") -> None:
    global _pipe_name
    pipe_name = str(pipe_name or "fssimx").strip()
    if not pipe_name:
        pipe_name = "fssimx"
    if not pipe_name.lower().startswith("\\\\.\\pipe\\"):
        pipe_name = rf"\\.\pipe\{pipe_name}"
    with _lock:
        changed = pipe_name != _pipe_name
        _pipe_name = pipe_name
    if changed:
        shutdown()


def get() -> dict[str, Any]:
    _ensure_worker()
    with _lock:
        return dict(_telemetry) if _telemetry else _default_data()


def shutdown() -> None:
    global _worker_thread, _current_handle, _telemetry_indexes
    _stop_event.set()
    _poke_pipe()
    thread = _worker_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=1.0)
    _close_current_handle()
    with _lock:
        _worker_thread = None
        _current_handle = None
        _telemetry = _default_data()
        _telemetry_indexes = {}
    _stop_event.clear()


def _ensure_worker() -> None:
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()


def _worker_loop() -> None:
    global _current_handle
    while not _stop_event.is_set():
        handle = _create_server_pipe()
        if handle == INVALID_HANDLE_VALUE:
            time.sleep(0.5)
            continue
        _current_handle = handle

        connected = _kernel32.ConnectNamedPipe(handle, None)
        if not connected:
            error = ctypes.get_last_error()
            if error != ERROR_PIPE_CONNECTED:
                _close_handle(handle)
                _current_handle = None
                if _stop_event.wait(0.3):
                    break
                continue

        try:
            while not _stop_event.is_set():
                message = _read_message(handle)
                if message is None:
                    break
                _process_message(message)
        finally:
            _mark_disconnected()
            _disconnect_pipe(handle)
            _close_handle(handle)
            _current_handle = None


def _create_server_pipe():
    return _kernel32.CreateNamedPipeW(
        _pipe_name,
        PIPE_ACCESS_INBOUND,
        PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
        MAX_INSTANCES,
        0,
        BUFFER_SIZE,
        0,
        None,
    )


def _read_message(handle: int) -> str | None:
    chunks: list[str] = []
    while not _stop_event.is_set():
        buffer = ctypes.create_string_buffer(BUFFER_SIZE)
        read = wintypes.DWORD()
        success = _kernel32.ReadFile(handle, buffer, BUFFER_SIZE, ctypes.byref(read), None)
        if read.value:
            chunks.append(buffer.raw[: read.value].decode("utf-8", errors="ignore"))
        if not success:
            error = ctypes.get_last_error()
            if error == ERROR_MORE_DATA:
                continue
            if error in {109, 232, 233}:
                return None
            return None
        if read.value == 0:
            return None
        if read.value < BUFFER_SIZE:
            break
    if not chunks:
        return None
    return "".join(chunks).rstrip("\0").strip()


def _process_message(message: str) -> None:
    global _telemetry_indexes
    if not message:
        return

    message = _normalize_message(message)
    if message.startswith("HEADER"):
        parts = [part for part in _split_fields(message)[1:] if part]
        indexes: dict[int, str] = {}
        for index, raw_key in enumerate(parts, start=1):
            indexes[index] = _to_snake_case(raw_key)
        with _lock:
            _telemetry_indexes = indexes
        return

    if not message.startswith("BODY"):
        return

    values = _split_fields(message)
    with _lock:
        telemetry = dict(_telemetry)
        indexes = dict(_telemetry_indexes)

    for index in range(1, len(values)):
        key = indexes.get(index)
        if not key:
            continue
        telemetry[key] = _parse_value(key, values[index])
    telemetry["connected"] = True

    with _lock:
        _telemetry.clear()
        _telemetry.update(telemetry)


def _mark_disconnected() -> None:
    with _lock:
        _telemetry.clear()
        _telemetry.update(_default_data())


def _to_snake_case(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return text.replace("__", "_").lower()


def _normalize_message(value: str) -> str:
    text = (value or "").strip().lstrip("\ufeff")
    text = text.replace("Ã‚Â¶", "¶")
    text = text.replace("Â¶", "¶")
    text = text.replace("Â§", "§")
    return text


def _split_fields(value: str) -> list[str]:
    return _normalize_message(value).split("§")


def _parse_value(key: str, value: str) -> Any:
    normalized = _normalize_message(value)
    if "¶" in normalized:
        values = [item for item in normalized.split("¶") if item != ""]
        return [_parse_scalar(key, item) for item in values]
    return _parse_scalar(key, normalized)


def _parse_scalar(key: str, value: str) -> Any:
    if _is_boolean_key(key):
        return value.strip() == "1"
    text = value.strip()
    if not text:
        return 0
    try:
        number = float(text)
    except ValueError:
        return text
    if "." not in text:
        return int(number)
    return number


def _is_boolean_key(key: str) -> bool:
    return key.startswith("is_") or key.endswith(("_enabled", "_on", "_started", "_active", "_selected", "_lowered", "_turned_on"))


def _disconnect_pipe(handle: int) -> None:
    try:
        _kernel32.DisconnectNamedPipe(handle)
    except Exception:
        pass


def _close_current_handle() -> None:
    global _current_handle
    handle = _current_handle
    if handle not in (None, INVALID_HANDLE_VALUE):
        _disconnect_pipe(handle)
        _close_handle(handle)
    _current_handle = None


def _close_handle(handle: int) -> None:
    if handle not in (None, INVALID_HANDLE_VALUE):
        _kernel32.CloseHandle(handle)


def _poke_pipe() -> None:
    try:
        handle = _kernel32.CreateFileW(
            _pipe_name,
            0x40000000,
            0,
            None,
            3,
            0,
            None,
        )
        if handle not in (None, INVALID_HANDLE_VALUE):
            _kernel32.CloseHandle(handle)
        elif ctypes.get_last_error() == ERROR_PIPE_BUSY:
            return
    except Exception:
        pass
