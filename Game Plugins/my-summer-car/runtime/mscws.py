from __future__ import annotations

import base64
import hashlib
import json
import socket
import struct
import threading
import time
from typing import Any
from urllib.parse import urlparse


STALE_TIMEOUT_SECONDS = 2.0
ACCEPT_TIMEOUT_SECONDS = 0.5

_url = "ws://127.0.0.1:2609"
_server_thread: threading.Thread | None = None
_stop_event = threading.Event()
_lock = threading.Lock()
_listener: socket.socket | None = None
_client: socket.socket | None = None
_client_connected = False
_last_data: dict[str, Any] = {}
_last_packet_time = 0.0
_last_error: str | None = None
_last_client = ""
_last_raw_message = ""
_last_event = "idle"


def _default_data() -> dict[str, Any]:
    return {
        "connected": False,
        "socket_error": _last_error,
        "socket_mode": "server",
        "last_client": _last_client,
        "last_raw_message": _last_raw_message,
        "_listener_event": _last_event,
    }


def configure(url: str = "ws://127.0.0.1:2609") -> None:
    global _url
    normalized = (url or "ws://127.0.0.1:2609").strip()
    if not normalized:
        normalized = "ws://127.0.0.1:2609"
    if normalized != _url:
        shutdown()
        _url = normalized
    _ensure_server()


def _ensure_server() -> None:
    global _server_thread
    if _server_thread is not None and _server_thread.is_alive():
        return
    _stop_event.clear()
    _server_thread = threading.Thread(target=_server_loop, daemon=True)
    _server_thread.start()


def _server_loop() -> None:
    global _listener, _last_error
    parsed = urlparse(_url)
    if parsed.scheme != "ws":
        _last_error = f"Somente ws:// e suportado: {_url}"
        return

    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 2609
    if host == "localhost":
        host = "127.0.0.1"

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind((host, port))
        listener.listen()
        listener.settimeout(ACCEPT_TIMEOUT_SECONDS)
        _listener = listener
        _last_error = None
        while not _stop_event.is_set():
            try:
                conn, address = listener.accept()
            except socket.timeout:
                continue
            except OSError as exc:
                if _stop_event.is_set():
                    break
                _last_error = str(exc)
                continue
            _handle_client(conn, address)
    except OSError as exc:
        _last_error = f"Falha ao iniciar servidor WebSocket em {host}:{port}: {exc}"
    finally:
        _listener = None
        try:
            listener.close()
        except OSError:
            pass


def _handle_client(conn: socket.socket, address: tuple[str, int]) -> None:
    global _client, _client_connected, _last_error, _last_client, _last_event
    conn.settimeout(1.0)
    _client = conn
    try:
        _handshake(conn)
        _last_error = None
        _last_client = f"{address[0]}:{address[1]}"
        _client_connected = True
        _last_event = "connected"
        fragmented_opcode: int | None = None
        fragmented_parts: list[bytes] = []
        while not _stop_event.is_set():
            fin, opcode, payload = _recv_frame(conn)
            if opcode == 0x0:
                if fragmented_opcode is None:
                    continue
                fragmented_parts.append(payload)
                if not fin:
                    continue
                opcode = fragmented_opcode
                payload = b"".join(fragmented_parts)
                fragmented_opcode = None
                fragmented_parts = []
            elif opcode in {0x1, 0x2} and not fin:
                fragmented_opcode = opcode
                fragmented_parts = [payload]
                continue
            if opcode in {0x1, 0x2}:
                _store_payload(payload.decode("utf-8", errors="replace").strip("\x00\r\n\t "), address)
            elif opcode == 0x8:
                _send_frame(conn, 0x8, b"")
                return
            elif opcode == 0x9:
                _send_frame(conn, 0xA, payload)
    except Exception as exc:
        if not _stop_event.is_set():
            _last_error = str(exc)
    finally:
        if _client is conn:
            _client = None
        _client_connected = False
        if not _stop_event.is_set():
            _last_event = "waiting_client"
        try:
            conn.close()
        except OSError:
            pass


def _handshake(conn: socket.socket) -> None:
    request = b""
    while b"\r\n\r\n" not in request:
        chunk = conn.recv(4096)
        if not chunk:
            raise RuntimeError("Cliente fechou durante o handshake.")
        request += chunk

    header_text = request.decode("latin1", errors="replace")
    lines = header_text.split("\r\n")
    if not lines or "GET " not in lines[0]:
        raise RuntimeError("Handshake HTTP invalido.")

    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        headers[key.lower()] = value.strip()

    ws_key = headers.get("sec-websocket-key", "")
    if not ws_key:
        raise RuntimeError("Cliente nao enviou Sec-WebSocket-Key.")

    accept_value = base64.b64encode(
        hashlib.sha1((ws_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
    ).decode("ascii")
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_value}\r\n\r\n"
    )
    conn.sendall(response.encode("ascii"))


def _recv_exact(conn: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise RuntimeError("Conexao WebSocket encerrada.")
        data.extend(chunk)
    return bytes(data)


def _recv_frame(conn: socket.socket) -> tuple[bool, int, bytes]:
    try:
        header = _recv_exact(conn, 2)
    except socket.timeout:
        return False, 0x0, b""

    first, second = header
    fin = bool(first & 0x80)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F

    if length == 126:
        length = struct.unpack("!H", _recv_exact(conn, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(conn, 8))[0]

    mask = _recv_exact(conn, 4) if masked else b""
    payload = _recv_exact(conn, length) if length else b""
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return fin, opcode, payload


def _send_frame(conn: socket.socket, opcode: int, payload: bytes) -> None:
    first = 0x80 | (opcode & 0x0F)
    length = len(payload)
    if length < 126:
        header = bytes([first, length])
    elif length < 65536:
        header = bytes([first, 126]) + struct.pack("!H", length)
    else:
        header = bytes([first, 127]) + struct.pack("!Q", length)
    conn.sendall(header + payload)


def _store_payload(message: str, address: tuple[str, int]) -> None:
    global _last_data, _last_packet_time, _last_error, _last_client, _last_raw_message, _last_event
    _last_raw_message = message[:500]
    try:
        data = json.loads(message)
    except json.JSONDecodeError as exc:
        _last_error = f"Payload JSON invalido: {exc.msg} na posicao {exc.pos}"
        _last_event = "listener_error"
        raise
    with _lock:
        payload = dict(data)
        payload["connected"] = True
        payload["socket_mode"] = "server"
        payload["last_client"] = f"{address[0]}:{address[1]}"
        payload["last_raw_message"] = _last_raw_message
        payload["_listener_event"] = "receiving"
        _last_data = payload
        _last_packet_time = time.monotonic()
        _last_client = payload["last_client"]
        _last_error = None
        _last_event = "receiving"


def get() -> dict[str, Any]:
    _ensure_server()
    with _lock:
        if not _last_data or (time.monotonic() - _last_packet_time) > STALE_TIMEOUT_SECONDS:
            data = _default_data()
            data["socket_error"] = _last_error
            if _last_error:
                data["_listener_event"] = "listener_error"
            elif _client_connected:
                data["_listener_event"] = "connected"
            else:
                data["_listener_event"] = _last_event
            return data
        data = dict(_last_data)
        data["socket_error"] = _last_error
        return data


def shutdown() -> None:
    global _server_thread, _listener, _client, _client_connected, _last_data, _last_packet_time, _last_error, _last_client, _last_raw_message, _last_event
    _stop_event.set()

    listener = _listener
    if listener is not None:
        try:
            listener.close()
        except OSError:
            pass
    _listener = None

    client = _client
    _client = None
    _client_connected = False
    if client is not None:
        try:
            client.close()
        except OSError:
            pass

    thread = _server_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=1.0)
    _server_thread = None

    with _lock:
        _last_data = {}
        _last_packet_time = 0.0
    _last_error = None
    _last_client = ""
    _last_raw_message = ""
    _last_event = "idle"
    _stop_event.clear()
