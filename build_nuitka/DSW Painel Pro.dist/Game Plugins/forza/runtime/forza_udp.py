from __future__ import annotations

import math
import os
import socket
import struct
import time
from typing import Any


SUPPORTED_PACKET_SIZES = {232, 311, 324, 331}
SLED_SIZE = 232
FM_DASH_BASE = 232
HORIZON_DASH_BASE = 244
STALE_TIMEOUT_SECONDS = 2.0

_bind_ip = os.getenv("FORZA_UDP_IP", "0.0.0.0")
try:
    _bind_port = int(os.getenv("FORZA_UDP_PORT", "9999"))
except ValueError:
    _bind_port = 9999

_udp_socket: socket.socket | None = None
_last_packet_time = 0.0
_last_data: dict[str, Any] = {}
_last_bind_attempt = 0.0
_socket_error: str | None = None


def _read_i32(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<i", packet, offset)[0]


def _read_u32(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<I", packet, offset)[0]


def _read_u16(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<H", packet, offset)[0]


def _read_u8(packet: bytes, offset: int) -> int:
    return packet[offset]


def _read_i8(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<b", packet, offset)[0]


def _read_f32(packet: bytes, offset: int) -> float:
    return struct.unpack_from("<f", packet, offset)[0]


def _read_vec3(packet: bytes, offset: int) -> list[float]:
    return list(struct.unpack_from("<3f", packet, offset))


def _read_wheel_f32(packet: bytes, offset: int) -> list[float]:
    return list(struct.unpack_from("<4f", packet, offset))


def _read_wheel_i32(packet: bytes, offset: int) -> list[int]:
    return list(struct.unpack_from("<4i", packet, offset))


def _fahrenheit_to_celsius(value: float) -> float:
    return (value - 32.0) * 5.0 / 9.0


def _default_data() -> dict[str, Any]:
    return {
        "connected": False,
        "packet_format": "none",
        "is_race_on": False,
        "timestamp_ms": 0,
        "engine_max_rpm": 0.0,
        "engine_idle_rpm": 0.0,
        "current_engine_rpm": 0.0,
        "acceleration": [0.0, 0.0, 0.0],
        "velocity": [0.0, 0.0, 0.0],
        "angular_velocity": [0.0, 0.0, 0.0],
        "yaw": 0.0,
        "pitch": 0.0,
        "roll": 0.0,
        "normalized_suspension_travel": [0.0, 0.0, 0.0, 0.0],
        "tire_slip_ratio": [0.0, 0.0, 0.0, 0.0],
        "wheel_rotation_speed": [0.0, 0.0, 0.0, 0.0],
        "wheel_on_rumble_strip": [False, False, False, False],
        "wheel_in_puddle": [0.0, 0.0, 0.0, 0.0],
        "surface_rumble": [0.0, 0.0, 0.0, 0.0],
        "tire_slip_angle": [0.0, 0.0, 0.0, 0.0],
        "tire_combined_slip": [0.0, 0.0, 0.0, 0.0],
        "suspension_travel_m": [0.0, 0.0, 0.0, 0.0],
        "car_ordinal": 0,
        "car_class": 0,
        "performance_index": 0,
        "drivetrain_type": 0,
        "num_cylinders": 0,
        "car_group": 0,
        "smashable_velocity_difference": 0.0,
        "smashable_mass": 0.0,
        "position": [0.0, 0.0, 0.0],
        "speed_mps": 0.0,
        "power_w": 0.0,
        "torque_nm": 0.0,
        "tire_temperature_c": [0.0, 0.0, 0.0, 0.0],
        "boost_psi": 0.0,
        "fuel": 0.0,
        "distance_traveled_m": 0.0,
        "best_lap": 0.0,
        "last_lap": 0.0,
        "current_lap": 0.0,
        "current_race_time": 0.0,
        "lap_number": 0,
        "race_position": 0,
        "accel": 0.0,
        "brake": 0.0,
        "clutch": 0.0,
        "handbrake": 0.0,
        "gear": None,
        "steer": 0.0,
        "normalized_driving_line": 0.0,
        "normalized_ai_brake_difference": 0.0,
        "tire_wear": [0.0, 0.0, 0.0, 0.0],
        "track_ordinal": 0,
        "socket_error": _socket_error,
    }


def _packet_format(packet_size: int) -> str:
    return {
        232: "sled",
        311: "dash_motorsport",
        324: "dash_horizon",
        331: "dash_motorsport_extended",
    }[packet_size]


def parse_packet(packet: bytes) -> dict[str, Any] | None:
    packet_size = len(packet)
    if packet_size not in SUPPORTED_PACKET_SIZES:
        return None

    velocity = _read_vec3(packet, 32)
    data = _default_data()
    data.update({
        "connected": True,
        "packet_format": _packet_format(packet_size),
        "is_race_on": _read_i32(packet, 0) != 0,
        "timestamp_ms": _read_u32(packet, 4),
        "engine_max_rpm": _read_f32(packet, 8),
        "engine_idle_rpm": _read_f32(packet, 12),
        "current_engine_rpm": _read_f32(packet, 16),
        "acceleration": _read_vec3(packet, 20),
        "velocity": velocity,
        "angular_velocity": _read_vec3(packet, 44),
        "yaw": _read_f32(packet, 56),
        "pitch": _read_f32(packet, 60),
        "roll": _read_f32(packet, 64),
        "normalized_suspension_travel": _read_wheel_f32(packet, 68),
        "tire_slip_ratio": _read_wheel_f32(packet, 84),
        "wheel_rotation_speed": _read_wheel_f32(packet, 100),
        "wheel_on_rumble_strip": [value != 0 for value in _read_wheel_i32(packet, 116)],
        "wheel_in_puddle": _read_wheel_f32(packet, 132),
        "surface_rumble": _read_wheel_f32(packet, 148),
        "tire_slip_angle": _read_wheel_f32(packet, 164),
        "tire_combined_slip": _read_wheel_f32(packet, 180),
        "suspension_travel_m": _read_wheel_f32(packet, 196),
        "car_ordinal": _read_i32(packet, 212),
        "car_class": _read_i32(packet, 216),
        "performance_index": _read_i32(packet, 220),
        "drivetrain_type": _read_i32(packet, 224),
        "num_cylinders": _read_i32(packet, 228),
        "speed_mps": math.sqrt(sum(component * component for component in velocity)),
        "socket_error": None,
    })

    if packet_size == 324:
        # No FH4/FH5 esses 12 bytes eram tratados como um intervalo extra.
        # No FH6 foram oficialmente definidos como CarGroup, SmashableVelDiff e SmashableMass.
        data["car_group"] = _read_u32(packet, 232)
        data["smashable_velocity_difference"] = _read_f32(packet, 236)
        data["smashable_mass"] = _read_f32(packet, 240)
        dash_base = HORIZON_DASH_BASE
    elif packet_size in {311, 331}:
        dash_base = FM_DASH_BASE
    else:
        dash_base = None

    if dash_base is not None:
        tire_temp_f = _read_wheel_f32(packet, dash_base + 24)
        data.update({
            "position": _read_vec3(packet, dash_base),
            "speed_mps": _read_f32(packet, dash_base + 12),
            "power_w": _read_f32(packet, dash_base + 16),
            "torque_nm": _read_f32(packet, dash_base + 20),
            "tire_temperature_c": [_fahrenheit_to_celsius(value) for value in tire_temp_f],
            "boost_psi": _read_f32(packet, dash_base + 40),
            "fuel": _read_f32(packet, dash_base + 44),
            "distance_traveled_m": _read_f32(packet, dash_base + 48),
            "best_lap": _read_f32(packet, dash_base + 52),
            "last_lap": _read_f32(packet, dash_base + 56),
            "current_lap": _read_f32(packet, dash_base + 60),
            "current_race_time": _read_f32(packet, dash_base + 64),
            "lap_number": _read_u16(packet, dash_base + 68),
            "race_position": _read_u8(packet, dash_base + 70),
            "accel": _read_u8(packet, dash_base + 71) / 255.0,
            "brake": _read_u8(packet, dash_base + 72) / 255.0,
            "clutch": _read_u8(packet, dash_base + 73) / 255.0,
            "handbrake": _read_u8(packet, dash_base + 74) / 255.0,
            "gear": _read_u8(packet, dash_base + 75),
            "steer": max(-1.0, min(1.0, _read_i8(packet, dash_base + 76) / 127.0)),
            "normalized_driving_line": max(-1.0, min(1.0, _read_i8(packet, dash_base + 77) / 127.0)),
            "normalized_ai_brake_difference": max(-1.0, min(1.0, _read_i8(packet, dash_base + 78) / 127.0)),
        })

    if packet_size == 331:
        data["tire_wear"] = _read_wheel_f32(packet, 311)
        data["track_ordinal"] = _read_i32(packet, 327)

    return data


def _build_socket(ip: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except OSError:
        pass
    sock.bind((ip, port))
    sock.setblocking(False)
    return sock


def _ensure_socket() -> None:
    global _udp_socket, _last_bind_attempt, _socket_error
    if _udp_socket is not None:
        return

    now = time.monotonic()
    if now - _last_bind_attempt < 2.0:
        return
    _last_bind_attempt = now

    try:
        _udp_socket = _build_socket(_bind_ip, _bind_port)
        _socket_error = None
    except OSError as exc:
        _udp_socket = None
        _socket_error = str(exc)


def _receive_latest() -> bytes | None:
    _ensure_socket()
    if _udp_socket is None:
        return None

    latest: bytes | None = None
    while True:
        try:
            payload, _address = _udp_socket.recvfrom(2048)
            latest = payload
        except BlockingIOError:
            break
        except OSError:
            break
    return latest


def configure(ip: str = "0.0.0.0", port: int = 9999) -> None:
    global _bind_ip, _bind_port
    normalized_ip = ip.strip() or "0.0.0.0"
    normalized_port = int(port)
    if not 1 <= normalized_port <= 65535:
        normalized_port = 9999

    if normalized_ip != _bind_ip or normalized_port != _bind_port:
        shutdown()
        _bind_ip = normalized_ip
        _bind_port = normalized_port


def iniciada(ip: str = "0.0.0.0", port: int = 9999) -> None:
    # Alias mantido para compatibilidade com o runtime do plugin LFS.
    configure(ip, port)


def get() -> dict[str, Any]:
    global _last_data, _last_packet_time

    payload = _receive_latest()
    if payload is not None:
        parsed = parse_packet(payload)
        if parsed is not None:
            _last_data = parsed
            _last_packet_time = time.monotonic()

    if not _last_data or (time.monotonic() - _last_packet_time) > STALE_TIMEOUT_SECONDS:
        data = _default_data()
        data["socket_error"] = _socket_error
        return data

    return dict(_last_data)


def shutdown() -> None:
    global _udp_socket, _last_packet_time, _last_data, _last_bind_attempt
    if _udp_socket is not None:
        try:
            _udp_socket.close()
        except OSError:
            pass
    _udp_socket = None
    _last_packet_time = 0.0
    _last_data = {}
    _last_bind_attempt = 0.0
