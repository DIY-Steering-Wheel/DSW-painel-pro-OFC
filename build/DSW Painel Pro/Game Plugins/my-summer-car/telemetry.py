from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


_runtime_module = None


def _runtime():
    global _runtime_module
    if _runtime_module is None:
        runtime_path = Path(__file__).resolve().parent / "runtime" / "mscws.py"
        spec = importlib.util.spec_from_file_location("my_summer_car_runtime", runtime_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Nao foi possivel carregar o runtime: {runtime_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _runtime_module = module
    return _runtime_module


def _first(data: dict[str, Any], *keys: str, default: Any = 0) -> Any:
    for key in keys:
        if key in data and data.get(key) is not None:
            return data.get(key)
    return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
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


def _ratio(value: Any) -> float:
    result = _float(value)
    if result > 1.0:
        result /= 100.0
    if result < 0.0:
        return 0.0
    if result > 1.0:
        return 1.0
    return round(result, 4)


def _speed(raw_speed: Any, unit: str) -> int:
    speed_kmh = _float(raw_speed)
    if unit == "KM/H":
        return int(round(speed_kmh))
    if unit in {"MPH", "MI/H"}:
        return int(round(speed_kmh * 0.6213711922))
    return int(round(speed_kmh / 3.6))


def _fuel_percent(value: Any) -> int:
    fuel = _float(value)
    if 0.0 <= fuel <= 1.0:
        fuel *= 100.0
    if fuel < 0.0:
        fuel = 0.0
    if fuel > 100.0:
        fuel = 100.0
    return int(round(fuel))


def _temperature(value_c: Any, unit: str) -> float:
    celsius = _float(value_c)
    if unit == "Fahrenheit":
        return round((celsius * 9.0 / 5.0) + 32.0, 1)
    return round(celsius, 1)


def _pressure(value_bar: Any, unit: str) -> float:
    bar = _float(value_bar)
    if unit == "PSI":
        return round(bar * 14.5037738, 2)
    return round(bar, 2)


def _gear(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized == "R":
            return -1
        if normalized in {"N", ""}:
            return 0
        try:
            return int(normalized)
        except ValueError:
            return 0
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 0
    if numeric < 0:
        return -1
    return numeric


def collect(settings: dict) -> dict:
    module = _runtime()
    module.configure(str(settings.get("url", "ws://127.0.0.1:2609")))
    data = module.get()

    speed_unit = str(settings.get("speed_unit", "KM/H"))
    pressure_unit = str(settings.get("pressure_unit", "BAR"))
    temperature_unit = str(settings.get("temperature_unit", "Celsius"))

    water_temp = _first(data, "water_temperature", "waterTemp", "coolant_temp", "coolantTemperature")
    oil_temp = _first(data, "oil_temperature", "oilTemp")
    oil_pressure = _first(data, "oil_pressure", "oilPressure")
    battery_warning = _first(data, "battery_warning", "batteryWarning", "battery_voltage_warning", default=False)

    return {
        "engine_rpm": int(round(_float(_first(data, "rpm", "engine_rpm")))),
        "current_gear": _gear(_first(data, "gear", "currentGear")),
        "speed": _speed(_first(data, "speed", "speedKmh", "speed_kmh"), speed_unit),
        "water_temperature": _temperature(water_temp, temperature_unit),
        "electric_enabled": _bool(_first(data, "electric_enabled", "ignition", "electrics", default=True)),
        "engine_enabled": _bool(_first(data, "engine_enabled", "engine_running", "running", default=False)),
        "fuel_percent": _fuel_percent(_first(data, "fuel", "fuel_percent", "fuelLevel")),
        "clutch": _ratio(_first(data, "clutch", "clutch_input")),
        "brake": _ratio(_first(data, "brake", "brake_input")),
        "throttle": _ratio(_first(data, "throttle", "gas", "accel")),
        "connected": _bool(data.get("connected")),
        "oil_temperature": _temperature(oil_temp, temperature_unit),
        "oil_pressure": _pressure(oil_pressure, pressure_unit),
        "battery_voltage_warning": _bool(battery_warning),
        "park_brake": _bool(_first(data, "park_brake", "handbrake")),
        "lights_parking": _bool(_first(data, "lights_parking", "parking_lights")),
        "lights_low_beam": _bool(_first(data, "lights_low_beam", "low_beam")),
        "lights_high_beam": _bool(_first(data, "lights_high_beam", "high_beam")),
        "blinker_left_active": _bool(_first(data, "blinker_left_active", "left_blinker")),
        "blinker_right_active": _bool(_first(data, "blinker_right_active", "right_blinker")),
        "traction_control": _bool(_first(data, "traction_control", "tc")),
        "abs": _bool(_first(data, "abs")),
        "acceleration_x": round(_float(_first(data, "acceleration_x", "accel_x")), 4),
        "acceleration_y": round(_float(_first(data, "acceleration_y", "accel_y")), 4),
        "acceleration_z": round(_float(_first(data, "acceleration_z", "accel_z")), 4),
        "raw_speed": _float(_first(data, "speed", "speedKmh", "speed_kmh")),
        "raw_gear": _first(data, "gear", "currentGear", default=""),
    }


def is_active(settings: dict) -> bool:
    module = _runtime()
    module.configure(str(settings.get("url", "ws://127.0.0.1:2609")))
    return bool(module.get().get("connected"))


def shutdown() -> None:
    module = _runtime_module
    if module is not None and hasattr(module, "shutdown"):
        module.shutdown()
