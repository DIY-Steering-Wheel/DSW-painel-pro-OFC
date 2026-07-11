from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


_runtime_module = None


def _runtime():
    global _runtime_module
    if _runtime_module is None:
        runtime_path = Path(__file__).resolve().parent / "runtime" / "dirt_udp.py"
        spec = importlib.util.spec_from_file_location("dirt_rally_runtime", runtime_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Nao foi possivel carregar o runtime: {runtime_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _runtime_module = module
    return _runtime_module


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _speed(value_mps: Any, unit: str) -> int:
    value = _float(value_mps)
    if unit == "KM/H":
        return int(round(value * 3.6))
    if unit in {"MPH", "MI/H"}:
        return int(round(value * 2.2369362921))
    return int(round(value))


def _pressure(value_psi: Any, unit: str) -> float:
    value = _float(value_psi)
    if unit == "BAR":
        return round(value * 0.0689475729, 2)
    return round(value, 2)


def collect(settings: dict) -> dict:
    module = _runtime()
    bind_ip = str(settings.get("telemetry_ip", settings.get("udp_ip", "0.0.0.0")))
    port = int(settings.get("telemetry_port", settings.get("udp_port", 10001)))
    module.configure(bind_ip, port)
    data = module.get()
    return {
        "connected": bool(data.get("connected")),
        "engine_rpm": _int(data.get("engine_rpm")),
        "current_gear": _int(data.get("gear")),
        "speed": _speed(data.get("speed"), str(settings.get("speed_unit", "KM/H"))),
        "pressure": _pressure(data.get("wheel_pressure"), str(settings.get("pressure_unit", "BAR"))),
        "throttle": round(_float(data.get("throttle")), 4),
        "brake": round(_float(data.get("brake")), 4),
        "clutch": round(_float(data.get("clutch")), 4),
        "steering": round(_float(data.get("steer")), 4),
        "acceleration_x": round(_float(data.get("gforce_lat")), 4),
        "acceleration_y": 0.0,
        "acceleration_z": round(_float(data.get("gforce_lon")), 4),
        "engine_enabled": _int(data.get("engine_rpm")) > 50,
        "electric_enabled": bool(data.get("connected")),
        "current_lap_time": round(_float(data.get("lap_time")), 3),
        "last_lap_time": round(_float(data.get("last_lap_time")), 3),
        "lap_number": _int(data.get("lap")),
        "race_position": _int(data.get("car_position")),
        "race_time": round(_float(data.get("time")), 3),
        "distance_traveled": round(_float(data.get("total_distance")), 2),
        "fuel_current": round(_float(data.get("fuel_in_tank")), 2),
        "fuel_capacity": round(_float(data.get("fuel_capacity")), 2),
        "traction_control": _int(data.get("traction_control")) > 0,
        "abs": _int(data.get("anti_lock_brakes")) > 0,
        "engine_max_rpm": _int(data.get("max_rpm")),
        "engine_rpm_min": _int(data.get("idle_rpm")),
        "map_position_x": round(_float(data.get("position_x")), 3),
        "map_position_y": round(_float(data.get("position_y")), 3),
        "map_position_z": round(_float(data.get("position_z")), 3),
        "raw_gear": _int(data.get("raw_gear")),
    }


def is_active(settings: dict) -> bool:
    module = _runtime()
    bind_ip = str(settings.get("telemetry_ip", settings.get("udp_ip", "0.0.0.0")))
    port = int(settings.get("telemetry_port", settings.get("udp_port", 10001)))
    module.configure(bind_ip, port)
    return bool(module.get().get("connected"))


def shutdown() -> None:
    module = _runtime_module
    if module is not None and hasattr(module, "shutdown"):
        module.shutdown()
