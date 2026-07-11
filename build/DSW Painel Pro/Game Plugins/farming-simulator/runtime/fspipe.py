from __future__ import annotations

import ctypes
import re
import threading
import time
from ctypes import wintypes
from typing import Any


PIPE_ACCESS_INBOUND = 0x00000001
PIPE_TYPE_MESSAGE = 0x00000004
PIPE_READMODE_MESSAGE = 0x00000002
PIPE_WAIT = 0x00000000
PIPE_UNLIMITED_INSTANCES = 255
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
ERROR_BROKEN_PIPE = 109
ERROR_MORE_DATA = 234
ERROR_PIPE_CONNECTED = 535
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_CreateNamedPipeW = _kernel32.CreateNamedPipeW
_CreateNamedPipeW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
]
_CreateNamedPipeW.restype = wintypes.HANDLE

_ConnectNamedPipe = _kernel32.ConnectNamedPipe
_ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
_ConnectNamedPipe.restype = wintypes.BOOL

_DisconnectNamedPipe = _kernel32.DisconnectNamedPipe
_DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
_DisconnectNamedPipe.restype = wintypes.BOOL

_ReadFile = _kernel32.ReadFile
_ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
_ReadFile.restype = wintypes.BOOL

_CloseHandle = _kernel32.CloseHandle
_CloseHandle.argtypes = [wintypes.HANDLE]
_CloseHandle.restype = wintypes.BOOL

_CreateFileW = _kernel32.CreateFileW
_CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
_CreateFileW.restype = wintypes.HANDLE


STALE_TIMEOUT_SECONDS = 2.0

_pipe_name = "fssimx"
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()
_lock = threading.Lock()
_server_handle: int | None = None
_headers: list[str] = []
_last_data: dict[str, Any] = {}
_last_packet_time = 0.0
_last_error = ""


def _default_data() -> dict[str, Any]:
    return {
        "connected": False,
        "pipe_error": _last_error,
    }


def configure(pipe_name: str = "fssimx") -> None:
    global _pipe_name
    normalized = (pipe_name or "fssimx").strip() or "fssimx"
    if normalized != _pipe_name:
        shutdown()
        _pipe_name = normalized
    _ensure_worker()


def _ensure_worker() -> None:
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()


def _worker_loop() -> None:
    global _server_handle, _last_error
    while not _stop_event.is_set():
        handle = _CreateNamedPipeW(
            fr"\\.\pipe\{_pipe_name}",
            PIPE_ACCESS_INBOUND,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
            PIPE_UNLIMITED_INSTANCES,
            4096,
            4096,
            0,
            None,
        )
        if handle == INVALID_HANDLE_VALUE:
            _last_error = f"Falha ao criar pipe {_pipe_name}: {ctypes.get_last_error()}"
            time.sleep(1.0)
            continue

        _server_handle = handle
        connected = _ConnectNamedPipe(handle, None)
        error = ctypes.get_last_error()
        if not connected and error != ERROR_PIPE_CONNECTED:
            _last_error = f"Falha ao aguardar pipe {_pipe_name}: {error}"
            _close_current_handle()
            time.sleep(0.2)
            continue

        try:
            _last_error = ""
            while not _stop_event.is_set():
                message = _read_message(handle)
                if message is None:
                    break
                _process_message(message)
        finally:
            try:
                _DisconnectNamedPipe(handle)
            except Exception:
                pass
            _close_current_handle()


def _close_current_handle() -> None:
    global _server_handle
    if _server_handle is not None:
        try:
            _CloseHandle(_server_handle)
        except Exception:
            pass
        _server_handle = None


def _read_message(handle: int) -> str | None:
    chunks: list[bytes] = []
    while True:
        buffer = ctypes.create_string_buffer(4096)
        bytes_read = wintypes.DWORD(0)
        ok = _ReadFile(handle, buffer, len(buffer), ctypes.byref(bytes_read), None)
        if ok:
            if bytes_read.value:
                chunks.append(buffer.raw[: bytes_read.value])
            break
        error = ctypes.get_last_error()
        if error == ERROR_MORE_DATA:
            if bytes_read.value:
                chunks.append(buffer.raw[: bytes_read.value])
            continue
        if error == ERROR_BROKEN_PIPE:
            return None
        global _last_error
        _last_error = f"Falha na leitura do pipe {_pipe_name}: {error}"
        return None
    if not chunks:
        return ""
    payload = b"".join(chunks)
    return payload.decode("utf-8", errors="replace")


def _process_message(message: str) -> None:
    global _headers, _last_data, _last_packet_time
    normalized = message.replace("Â§", "§").replace("Â¶", "¶").strip()
    if not normalized:
        return
    parts = normalized.split("§")
    if len(parts) < 2:
        return
    kind = parts[0].strip().upper()
    values = parts[1:]
    if values and values[-1] == "":
        values = values[:-1]

    if kind == "HEADER":
        _headers = [_to_snake_case(item) for item in values]
        return

    if kind != "BODY" or not _headers:
        return

    telemetry: dict[str, Any] = {}
    for index, raw_value in enumerate(values):
        if index >= len(_headers):
            break
        key = _headers[index]
        telemetry[key] = _parse_value(key, raw_value)

    telemetry["connected"] = True
    with _lock:
        _last_data = telemetry
        _last_packet_time = time.monotonic()


def _to_snake_case(value: str) -> str:
    text = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value.strip())
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return text.replace("__", "_").lower()


def _parse_value(key: str, value: str) -> Any:
    text = (value or "").strip()
    if "¶" in text:
        items = [item for item in text.split("¶") if item != ""]
        return [_parse_scalar(key, item) for item in items]
    return _parse_scalar(key, text)


def _parse_scalar(key: str, value: str) -> Any:
    if _is_boolean_key(key):
        return value == "1"
    try:
        if any(token in value for token in (".", "e", "E")):
            return float(value)
        return int(value)
    except ValueError:
        return value


def _is_boolean_key(key: str) -> bool:
    return key.startswith("is_") or key.endswith(("_enabled", "_on", "_started", "_active", "_selected", "_lowered", "_turned_on"))


def get() -> dict[str, Any]:
    _ensure_worker()
    with _lock:
        if not _last_data or (time.monotonic() - _last_packet_time) > STALE_TIMEOUT_SECONDS:
            return _default_data()
        payload = dict(_last_data)
        payload["pipe_error"] = _last_error
        return payload


def shutdown() -> None:
    global _worker_thread, _last_data, _last_packet_time, _last_error, _headers
    _stop_event.set()
    _poke_pipe()
    thread = _worker_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=1.0)
    _worker_thread = None
    _close_current_handle()
    with _lock:
        _last_data = {}
        _last_packet_time = 0.0
    _headers = []
    _last_error = ""
    _stop_event.clear()


def _poke_pipe() -> None:
    handle = _CreateFileW(
        fr"\\.\pipe\{_pipe_name}",
        GENERIC_WRITE,
        0,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if handle != INVALID_HANDLE_VALUE:
        _CloseHandle(handle)
