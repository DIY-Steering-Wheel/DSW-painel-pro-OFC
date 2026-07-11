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


def _player_map_coordinates(graphics) -> tuple[float, float, float]:
    player_car_id = getattr(graphics, "player_car_id", None)
    car_ids = list(getattr(graphics, "car_id", []) or [])
    coordinates = list(getattr(graphics, "car_coordinates", []) or [])

    if player_car_id is not None:
        for index, car_id in enumerate(car_ids):
            if car_id == player_car_id and index < len(coordinates):
                vector = coordinates[index]
                if not any(math.isnan(getattr(vector, axis)) for axis in ("x", "y", "z")):
                    return float(vector.x), float(vector.y), float(vector.z)

    for vector in coordinates:
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
    map_position = _player_map_coordinates(sm.Graphics)
    water_temp = int(sm.Physics.water_temp)
    if settings["temperature_unit"] != "Celsius":
        water_temp = int((water_temp * 9 / 5) + 32)
    turbo = float(sm.Physics.turbo_boost)
    if settings["pressure_unit"] != "BAR":
        turbo *= 14.5038
    g_force = sm.Physics.g_force
    return {
        "engine_rpm": int(abs(sm.Physics.rpm)),
        "current_gear": sm.Physics.gear - 1,
        "speed": speed,
        "fuel_percent": fuel_percent,
        "water_temperature": water_temp,
        "turbo": round(turbo, 2),
        "abs": round(sm.Physics.abs_vibration, 2),
        "acceleration_x": round(float(g_force.x), 4),
        "acceleration_y": round(float(g_force.y), 4),
        "acceleration_z": round(float(g_force.z), 4),
        "map_position_x": round(map_position[0], 4),
        "map_position_y": round(map_position[1], 4),
        "map_position_z": round(map_position[2], 4),
    }
