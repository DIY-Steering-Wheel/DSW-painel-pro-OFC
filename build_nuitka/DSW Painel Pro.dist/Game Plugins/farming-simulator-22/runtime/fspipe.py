from __future__ import annotations

import re
import threading
import time
from typing import Any

import pywintypes
import win32file
import win32pipe


BUFFER_SIZE = 65536
MAX_INSTANCES = 10
_lock = threading.Lock()
_stop_event = threading.Event()
_worker_thread: threading.Thread | None = None
_pipe_name = r"\\.\pipe\fssimx"
_telemetry: dict[str, Any] = {"connected": False}
_telemetry_indexes: dict[int, str] = {}
_current_handle = None
_last_error = ""
_last_event = "idle"


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
        data = dict(_telemetry) if _telemetry else _default_data()
        data["_listener_error"] = _last_error
        data["_listener_event"] = _last_event
        return data


def peek() -> dict[str, Any]:
    with _lock:
        data = dict(_telemetry) if _telemetry else _default_data()
        data["_listener_error"] = _last_error
        data["_listener_event"] = _last_event
        return data


def shutdown() -> None:
    global _worker_thread, _current_handle, _telemetry_indexes, _last_error, _last_event
    _stop_event.set()
    _close_current_handle()
    thread = _worker_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=1.0)
    with _lock:
        _worker_thread = None
        _current_handle = None
        _telemetry = _default_data()
        _telemetry_indexes = {}
        _last_error = ""
        _last_event = "stopped"
    _stop_event.clear()


def _ensure_worker() -> None:
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()


def _worker_loop() -> None:
    global _current_handle, _last_error, _last_event
    while not _stop_event.is_set():
        handle = None
        try:
            with _lock:
                _last_event = "creating_pipe"
                _last_error = ""
            handle = win32pipe.CreateNamedPipe(
                _pipe_name,
                win32pipe.PIPE_ACCESS_INBOUND,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                MAX_INSTANCES,
                BUFFER_SIZE,
                BUFFER_SIZE,
                0,
                None,
            )
            _current_handle = handle
            with _lock:
                _last_event = "waiting_client"
            try:
                win32pipe.ConnectNamedPipe(handle, None)
            except pywintypes.error as exc:
                if exc.winerror != 535:
                    raise
            with _lock:
                _last_event = "connected"
                _last_error = ""

            while not _stop_event.is_set():
                message = _read_message(handle)
                if message is None:
                    break
                _process_message(message)
        except pywintypes.error as exc:
            with _lock:
                _last_error = f"{exc.winerror}: {exc.strerror}"
                _last_event = "listener_error"
            time.sleep(0.3)
        finally:
            _mark_disconnected()
            if handle is not None:
                try:
                    win32file.CloseHandle(handle)
                except Exception:
                    pass
            _current_handle = None


def _read_message(handle) -> str | None:
    chunks: list[str] = []
    while not _stop_event.is_set():
        try:
            _, data = win32file.ReadFile(handle, BUFFER_SIZE)
            if not data:
                return None
            chunks.append(data.decode("utf-8", errors="ignore"))
            break
        except pywintypes.error as exc:
            if exc.winerror == 234:
                if len(exc.args) >= 3 and isinstance(exc.args[2], (bytes, bytearray)):
                    chunks.append(bytes(exc.args[2]).decode("utf-8", errors="ignore"))
                continue
            if exc.winerror in {109, 232, 233}:
                return None
            return None
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
    global _last_event
    with _lock:
        _telemetry.clear()
        _telemetry.update(_default_data())
        if _last_event == "connected":
            _last_event = "disconnected"


def _to_snake_case(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return text.replace("__", "_").lower()


def _normalize_message(value: str) -> str:
    text = (value or "").strip().lstrip("\ufeff")
    return (
        text.replace("Ãƒâ€šÃ‚Â¶", "¶")
        .replace("Ã‚Â¶", "¶")
        .replace("Â¶", "¶")
        .replace("Ã‚Â§", "§")
        .replace("Â§", "§")
    )


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


def _close_current_handle() -> None:
    global _current_handle
    handle = _current_handle
    if handle is not None:
        try:
            win32file.CloseHandle(handle)
        except Exception:
            pass
    _current_handle = None
