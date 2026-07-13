from __future__ import annotations

import socket
import struct
import threading
import time
from typing import Any


_PACKET_FORMAT = "<64f"
_PACKET_SIZE = struct.calcsize(_PACKET_FORMAT)
_lock = threading.Lock()
_socket: socket.socket | None = None
_state: dict[str, Any] = {"connected": False}
_bind_ip = "0.0.0.0"
_bind_port = 10001
_last_packet_at = 0.0
_socket_error = ""


def configure(ip: str = "0.0.0.0", port: int = 10001) -> None:
    global _bind_ip, _bind_port
    target_ip = str(ip or "0.0.0.0")
    target_port = int(port or 10001)
    if target_ip != _bind_ip or target_port != _bind_port:
        shutdown()
        _bind_ip = target_ip
        _bind_port = target_port


def _build_socket(ip: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    except OSError:
        pass
    sock.bind((ip, port))
    sock.setblocking(False)
    return sock


def _ensure_socket() -> None:
    global _socket, _socket_error
    if _socket is None:
        try:
            _socket = _build_socket(_bind_ip, _bind_port)
            _socket_error = ""
        except OSError as exc:
            _socket = None
            _socket_error = str(exc)


def _recv_latest(sock: socket.socket) -> bytes | None:
    latest = None
    while True:
        try:
            payload, _addr = sock.recvfrom(4096)
            latest = payload
        except BlockingIOError:
            break
        except OSError:
            break
    return latest


def _normalize_gear(raw_value: float) -> int:
    value = int(round(raw_value))
    if value <= 0:
        return -1
    if value == 1:
        return 0
    return value - 1


def _parse_packet(packet: bytes) -> dict[str, Any] | None:
    if len(packet) < _PACKET_SIZE:
        return None
    values = struct.unpack_from(_PACKET_FORMAT, packet)
    raw_gear = int(round(values[33]))
    return {
        "connected": True,
        "time": values[0],
        "lap_time": values[1],
        "lap_distance": values[2],
        "total_distance": values[3],
        "position_x": values[4],
        "position_y": values[5],
        "position_z": values[6],
        "speed": values[7],
        "throttle": values[29],
        "steer": values[30],
        "brake": values[31],
        "clutch": values[32],
        "raw_gear": raw_gear,
        "gear": _normalize_gear(values[33]),
        "gforce_lat": values[34],
        "gforce_lon": values[35],
        "lap": values[36],
        "engine_rpm": values[37],
        "car_position": values[39],
        "traction_control": values[43],
        "anti_lock_brakes": values[44],
        "fuel_in_tank": values[45],
        "fuel_capacity": values[46],
        "last_lap_time": values[56],
        "max_rpm": values[57],
        "idle_rpm": values[58],
        "wheel_pressure": values[52],
    }


def get() -> dict[str, Any]:
    global _last_packet_at
    _ensure_socket()
    packet = _recv_latest(_socket) if _socket is not None else None
    if packet:
        parsed = _parse_packet(packet)
        if parsed is not None:
            with _lock:
                _state.clear()
                _state.update(parsed)
            _last_packet_at = time.time()
    with _lock:
        payload = dict(_state)
    if _socket is None:
        payload["connected"] = False
        if _socket_error:
            payload["socket_error"] = _socket_error
        return payload
    if not _last_packet_at or time.time() - _last_packet_at > 1.0:
        payload["connected"] = False
    return payload


def shutdown() -> None:
    global _socket, _last_packet_at, _socket_error
    sock = _socket
    if sock is not None:
        try:
            sock.close()
        except OSError:
            pass
    _socket = None
    _last_packet_at = 0.0
    _socket_error = ""
