from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import threading
import time
from typing import Any
from urllib.parse import urlparse


STALE_TIMEOUT_SECONDS = 2.0
RECONNECT_DELAY_SECONDS = 2.0

_url = os.getenv("MSC_TELEMETRY_URL", "ws://127.0.0.1:2609")
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()
_lock = threading.Lock()
_last_data: dict[str, Any] = {}
_last_packet_time = 0.0
_last_error: str | None = None


def _default_data() -> dict[str, Any]:
    return {
        "connected": False,
        "socket_error": _last_error,
    }


def configure(url: str = "ws://127.0.0.1:2609") -> None:
    global _url
    normalized = (url or "ws://127.0.0.1:2609").strip()
    if not normalized:
        normalized = "ws://127.0.0.1:2609"
    if normalized != _url:
        shutdown()
        _url = normalized
    _ensure_worker()


def _ensure_worker() -> None:
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()


def _worker_loop() -> None:
    global _last_error
    while not _stop_event.is_set():
        try:
            _read_forever()
            _last_error = None
        except Exception as exc:
            _last_error = str(exc)
        if _stop_event.wait(RECONNECT_DELAY_SECONDS):
            break


def _read_forever() -> None:
    parsed = urlparse(_url)
    if parsed.scheme != "ws":
        raise RuntimeError(f"Somente ws:// e suportado: {_url}")

    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    sock = socket.create_connection((host, port), timeout=3.0)
    sock.settimeout(1.0)
    try:
        _handshake(sock, host, port, path)
        while not _stop_event.is_set():
            opcode, payload = _recv_frame(sock)
            if opcode == 0x0:
                continue
            if opcode == 0x1:
                _store_payload(payload.decode("utf-8", errors="replace"))
            elif opcode == 0x8:
                _send_frame(sock, 0x8, b"")
                return
            elif opcode == 0x9:
                _send_frame(sock, 0xA, payload)
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _handshake(sock: socket.socket, host: str, port: int, path: str) -> None:
    nonce = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {nonce}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(request.encode("ascii"))

    response = b""
    while b"\r\n\r\n" not in response:
        chunk = sock.recv(4096)
        if not chunk:
            raise RuntimeError("Servidor WebSocket fechou durante o handshake.")
        response += chunk

    header_text = response.decode("latin1", errors="replace")
    if " 101 " not in header_text and not header_text.startswith("HTTP/1.1 101"):
        raise RuntimeError(f"Handshake WebSocket invalido: {header_text.splitlines()[0]}")

    expected_accept = base64.b64encode(
        hashlib.sha1((nonce + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
    ).decode("ascii")
    if f"Sec-WebSocket-Accept: {expected_accept}" not in header_text:
        raise RuntimeError("Resposta WebSocket sem chave de validacao esperada.")


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise RuntimeError("Conexao WebSocket encerrada.")
        data.extend(chunk)
    return bytes(data)


def _recv_frame(sock: socket.socket) -> tuple[int, bytes]:
    try:
        header = _recv_exact(sock, 2)
    except socket.timeout:
        return 0x0, b""

    first, second = header
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F

    if length == 126:
        length = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(sock, 8))[0]

    mask = _recv_exact(sock, 4) if masked else b""
    payload = _recv_exact(sock, length) if length else b""
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload


def _send_frame(sock: socket.socket, opcode: int, payload: bytes) -> None:
    first = 0x80 | (opcode & 0x0F)
    length = len(payload)
    mask = os.urandom(4)
    if length < 126:
        header = bytes([first, 0x80 | length])
    elif length < 65536:
        header = bytes([first, 0x80 | 126]) + struct.pack("!H", length)
    else:
        header = bytes([first, 0x80 | 127]) + struct.pack("!Q", length)
    masked_payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    sock.sendall(header + mask + masked_payload)


def _store_payload(message: str) -> None:
    global _last_data, _last_packet_time, _last_error
    data = json.loads(message)
    with _lock:
        payload = dict(data)
        payload["connected"] = True
        _last_data = payload
        _last_packet_time = time.monotonic()
        _last_error = None


def get() -> dict[str, Any]:
    _ensure_worker()
    with _lock:
        if not _last_data or (time.monotonic() - _last_packet_time) > STALE_TIMEOUT_SECONDS:
            data = _default_data()
            data["socket_error"] = _last_error
            return data
        data = dict(_last_data)
        data["socket_error"] = _last_error
        return data


def shutdown() -> None:
    global _worker_thread, _last_data, _last_packet_time, _last_error
    _stop_event.set()
    thread = _worker_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=1.0)
    _worker_thread = None
    with _lock:
        _last_data = {}
        _last_packet_time = 0.0
    _last_error = None
    _stop_event.clear()
