from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


_runtime_module = None


def _runtime():
    global _runtime_module
    if _runtime_module is None:
        runtime_path = Path(__file__).resolve().parent / "runtime" / "irsdk_runtime.py"
        spec = importlib.util.spec_from_file_location("iracing_runtime", runtime_path)
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
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _speed(value_mps: Any, unit: str) -> int:
    value = _float(value_mps)
    if unit == "KM/H":
        return int(round(value * 3.6))
    if unit in {"MPH", "MI/H"}:
        return int(round(value * 2.2369362921))
    return int(round(value))


def _temperature(value_c: Any, unit: str) -> float:
    value = _float(value_c)
    if unit == "Fahrenheit":
        return round((value * 9.0 / 5.0) + 32.0, 1)
    return round(value, 1)


def _pressure(value_kpa: Any, unit: str) -> float:
    value = _float(value_kpa)
    if unit == "BAR":
        return round(value / 100.0, 2)
    return round(value * 0.1450377377, 2)


def collect(settings: dict) -> dict:
    module = _runtime()
    data = module.get()
    speed_unit = str(settings.get("speed_unit", "KM/H"))
    temperature_unit = str(settings.get("temperature_unit", "Celsius"))
    pressure_unit = str(settings.get("pressure_unit", "BAR"))
    fuel_level = _float(data.get("fuel_level"))
    fuel_pct = _float(data.get("fuel_pct"))

    return {
        "connected": _bool(data.get("connected")),
        "sdk_available": _bool(data.get("sdk_available")),
        "engine_rpm": _int(data.get("rpm")),
        "current_gear": _int(data.get("gear")),
        "speed": _speed(data.get("speed"), speed_unit),
        "water_temperature": _temperature(data.get("water_temp"), temperature_unit),
        "fuel_percent": int(round(fuel_pct * 100.0)) if fuel_pct > 0 else int(round(fuel_level)),
        "clutch": round(_float(data.get("clutch")), 4),
        "brake": round(_float(data.get("brake")), 4),
        "throttle": round(_float(data.get("throttle")), 4),
        "engine_enabled": _int(data.get("rpm")) > 50,
        "electric_enabled": _bool(data.get("connected")),
        "park_brake": _bool(data.get("on_pit_road")),
        "acceleration_x": round(_float(data.get("lat_accel")), 4),
        "acceleration_y": round(_float(data.get("vert_accel")), 4),
        "acceleration_z": round(_float(data.get("long_accel")), 4),
        "oil_temperature": _temperature(data.get("oil_temp"), temperature_unit),
        "oil_pressure": _pressure(data.get("oil_press"), pressure_unit),
        "lap_number": _int(data.get("lap")),
        "best_lap_time": round(_float(data.get("lap_best")), 3),
        "last_lap_time": round(_float(data.get("lap_last")), 3),
        "current_lap_time": round(_float(data.get("lap_current")), 3),
        "race_position": _int(data.get("position")),
    }


def is_active(settings: dict) -> bool:
    return bool(_runtime().get().get("connected"))


def shutdown() -> None:
    module = _runtime_module
    if module is not None and hasattr(module, "shutdown"):
        module.shutdown()
