from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path


_runtime_module = None


def _runtime():
    global _runtime_module
    if _runtime_module is None:
        runtime_path = Path(__file__).resolve().parent / "runtime" / "pyaccsharedmemory.py"
        spec = importlib.util.spec_from_file_location("assetto_corsa_runtime", runtime_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _runtime_module = module
    return _runtime_module


def _first_valid_coordinates(vectors) -> tuple[float, float, float]:
    for vector in vectors:
        if any(math.isnan(getattr(vector, axis)) for axis in ("x", "y", "z")):
            continue
        if vector.x == 0 and vector.y == 0 and vector.z == 0:
            continue
        return float(vector.x), float(vector.y), float(vector.z)
    return 0.0, 0.0, 0.0


def collect(settings: dict) -> dict:
    module = _runtime()
    asm = module.accSharedMemory()
    sm = asm.read_shared_memory()
    if sm is None or getattr(sm, "Physics", None) is None or getattr(sm, "Static", None) is None or getattr(sm, "Graphics", None) is None:
        raise RuntimeError("Assetto Corsa não está com a telemetria disponível.")
    speed = int(sm.Physics.speed_kmh if settings["speed_unit"] == "KM/H" else sm.Physics.speed_kmh * 0.621371)
    fuel_percent = int((sm.Physics.fuel * 100) / sm.Static.max_fuel) if sm.Static.max_fuel else 0
    coords = _first_valid_coordinates(sm.Graphics.car_coordinates)
    water_temp = int(sm.Physics.water_temp)
    if settings["temperature_unit"] != "Celsius":
        water_temp = int((water_temp * 9 / 5) + 32)
    turbo = float(sm.Physics.turbo_boost)
    if settings["pressure_unit"] != "BAR":
        turbo *= 14.5038
    return {
        "engine_rpm": int(abs(sm.Physics.rpm)),
        "current_gear": sm.Physics.gear - 1,
        "speed": speed,
        "fuel_percent": fuel_percent,
        "water_temperature": water_temp,
        "turbo": round(turbo, 2),
        "abs": round(sm.Physics.abs_vibration, 2),
        "acceleration_x": coords[0],
        "acceleration_y": coords[1],
        "acceleration_z": coords[2],
    }
