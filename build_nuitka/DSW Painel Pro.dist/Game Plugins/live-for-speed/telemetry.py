from __future__ import annotations

import importlib.util
from pathlib import Path


_runtime_module = None


def _runtime():
    global _runtime_module
    if _runtime_module is None:
        runtime_path = Path(__file__).resolve().parent / "runtime" / "lfsudp.py"
        spec = importlib.util.spec_from_file_location("lfs_runtime", runtime_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        _runtime_module = module
    return _runtime_module


def collect(settings: dict) -> dict:
    module = _runtime()
    data = module.get()
    lights = data.get("bico_de_luz", {})
    speed = int(data.get("speed", 0) * 3.6 if settings["speed_unit"] == "KM/H" else data.get("speed", 0) * 2.236936)
    temp = int(data.get("engTemp", 0))
    return {
        "engine_rpm": int(data.get("rpm", 0)),
        "current_gear": data.get("gear", 0),
        "speed": speed,
        "water_temperature": temp if settings["temperature_unit"] == "Celsius" else (temp * 9 / 5) + 32,
        "park_brake": lights.get("handbrake", 0),
        "electric_enabled": data.get("ElectricEnabled", 0),
        "engine_enabled": data.get("EngineEnabled", 0),
        "blinker_left_active": lights.get("left_turn", 0),
        "blinker_right_active": lights.get("right_turn", 0),
        "lights_parking": lights.get("sidelights", 0),
        "lights_low_beam": lights.get("dipped_headlight", 0),
        "lights_high_beam": lights.get("full_beam", 0),
        "battery_voltage_warning": lights.get("battery_warn", 0),
        "oil_warning": lights.get("oil_warn", 0),
        "water_warning": False if temp < 104 else True,
        "fuel_percent": int(data.get("fuel", 0)),
        "clutch": data.get("clutch", 0),
        "brake": data.get("brake", 0),
        "throttle": data.get("throttle", 0),
        "turbo": round(data.get("turboPressure", 0), 2) if settings["pressure_unit"] == "BAR" else round(data.get("turboPressure", 0) * 14.5038, 2),
        "traction_control": lights.get("tc", False),
        "abs": lights.get("abs", 0),
        "oil_pressure": int(data.get("oilPressure", 0)) if settings["pressure_unit"] == "BAR" else round(data.get("oilPressure", 0) * 14.5038, 2),
        "oil_temperature": int(data.get("oilTemp", 0)) if settings["temperature_unit"] == "Celsius" else (int(data.get("oilTemp", 0)) * 9 / 5) + 32,
        "acceleration_x": data.get("x", 0),
        "acceleration_y": data.get("y", 0),
        "acceleration_z": data.get("z", 0),
    }


def shutdown() -> None:
    module = _runtime_module
    if module is not None and hasattr(module, "shutdown"):
        module.shutdown()
