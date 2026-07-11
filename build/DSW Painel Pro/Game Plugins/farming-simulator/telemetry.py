from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


_runtime_module = None
_IMPLEMENT_LIMIT = 8


def _runtime():
    global _runtime_module
    if _runtime_module is None:
        runtime_path = Path(__file__).resolve().parent / "runtime" / "fspipe.py"
        spec = importlib.util.spec_from_file_location("farming_simulator_runtime", runtime_path)
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


def _ratio(current: Any, maximum: Any) -> int:
    current_value = _float(current)
    maximum_value = _float(maximum)
    if maximum_value <= 0:
        return 0
    value = max(0.0, min(100.0, (current_value / maximum_value) * 100.0))
    return int(round(value))


def _speed(value_kmh: Any, unit: str) -> int:
    speed_kmh = _float(value_kmh)
    if unit == "KM/H":
        return int(round(speed_kmh))
    if unit in {"MPH", "MI/H"}:
        return int(round(speed_kmh * 0.6213711922))
    return int(round(speed_kmh / 3.6))


def _temperature(value_c: Any, unit: str) -> float:
    celsius = _float(value_c)
    if unit == "Fahrenheit":
        return round((celsius * 9.0 / 5.0) + 32.0, 1)
    return round(celsius, 1)


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _array_value(items: list[Any], index: int, caster) -> Any:
    if index >= len(items):
        return caster(0)
    return caster(items[index])


def _implements_payload(data: dict[str, Any]) -> dict[str, Any]:
    positions = _list(data.get("attached_implements_position"))
    lowered = _list(data.get("attached_implements_lowered"))
    selected = _list(data.get("attached_implements_selected"))
    turned_on = _list(data.get("attached_implements_turned_on"))
    wear = _list(data.get("attached_implements_wear"))
    implement_count = max(len(positions), len(lowered), len(selected), len(turned_on), len(wear))

    payload: dict[str, Any] = {
        "implements_count": implement_count,
        "implements_lowered_count": sum(1 for value in lowered if _bool(value)),
        "implements_selected_count": sum(1 for value in selected if _bool(value)),
        "implements_turned_on_count": sum(1 for value in turned_on if _bool(value)),
        "implements_avg_wear": round(sum(_float(value) for value in wear) / len(wear), 2) if wear else 0.0,
    }

    for index in range(_IMPLEMENT_LIMIT):
        slot = index + 1
        payload[f"implements_position_{slot}"] = _array_value(positions, index, _int)
        payload[f"implements_lowered_{slot}"] = _array_value(lowered, index, _bool)
        payload[f"implements_selected_{slot}"] = _array_value(selected, index, _bool)
        payload[f"implements_turned_on_{slot}"] = _array_value(turned_on, index, _bool)
        payload[f"implements_wear_{slot}"] = round(_array_value(wear, index, _float), 2)
    return payload


def collect(settings: dict) -> dict:
    module = _runtime()
    module.configure(str(settings.get("pipe_name", "fssimx")))
    data = module.get()

    speed_unit = str(settings.get("speed_unit", "KM/H"))
    temperature_unit = str(settings.get("temperature_unit", "Celsius"))
    engine_started = _bool(data.get("is_engine_started"))
    light_on = _bool(data.get("is_light_on"))
    high_beam = _bool(data.get("is_light_high_on"))
    beacon_on = _bool(data.get("is_light_beacon_on"))

    payload = {
        "engine_rpm": _int(data.get("rpm")),
        "current_gear": -_int(data.get("gear")) if _bool(data.get("is_reverse_driving")) and _int(data.get("gear")) > 0 else _int(data.get("gear")),
        "speed": _speed(data.get("speed"), speed_unit),
        "water_temperature": _temperature(data.get("motor_temperature"), temperature_unit),
        "electric_enabled": engine_started or light_on or high_beam or beacon_on,
        "engine_enabled": engine_started,
        "lights_parking": light_on,
        "lights_low_beam": light_on,
        "lights_high_beam": high_beam,
        "blinker_left_active": _bool(data.get("is_light_turn_left_on")),
        "blinker_right_active": _bool(data.get("is_light_turn_right_on")),
        "hazard_warning_lights": _bool(data.get("is_light_hazard_on")),
        "park_brake": _bool(data.get("is_hand_brake_on")),
        "fuel_percent": _ratio(data.get("fuel"), data.get("fuel_max")),

        "connected": _bool(data.get("connected")),
        "wear_percent": round(_float(data.get("wear")), 2),
        "operation_time_minutes": _int(data.get("operation_time_minutes")),
        "fuel_current": round(_float(data.get("fuel")), 2),
        "fuel_capacity": round(_float(data.get("fuel_max")), 2),
        "fuel_type_code": _int(data.get("fuel_type")),
        "engine_rpm_min": _int(data.get("rpm_min")),
        "engine_rpm_max": _int(data.get("rpm_max")),
        "cruise_control": _bool(data.get("is_cruise_control_on")),
        "cruise_control_speed": _int(data.get("cruise_control_speed")),
        "cruise_control_max_speed": _int(data.get("cruise_control_max_speed")),
        "ai_active": _bool(data.get("is_ai_active")),
        "reverse_driving": _bool(data.get("is_reverse_driving")),
        "motor_fan_enabled": _bool(data.get("is_motor_fan_enabled")),
        "vehicle_price": round(_float(data.get("vehicle_price")), 2),
        "vehicle_sell_price": round(_float(data.get("vehicle_sell_price")), 2),
        "honk_on": _bool(data.get("is_honk_on")),
        "beacon_on": beacon_on,
        "hazard_on": _bool(data.get("is_light_hazard_on")),
        "wipers_on": _bool(data.get("is_wipers_on")),
        "angle_rotation": round(_float(data.get("angle_rotation")), 2),
        "mass": round(_float(data.get("mass")), 2),
        "total_mass": round(_float(data.get("total_mass")), 2),
        "on_field": _bool(data.get("is_on_field")),
        "def_level": round(_float(data.get("def")), 2),
        "def_capacity": round(_float(data.get("def_max")), 2),
        "air_level": round(_float(data.get("air")), 2),
        "air_capacity": round(_float(data.get("air_max")), 2),
        "money": round(_float(data.get("money")), 2),
        "temperature_min": _temperature(data.get("temperature_min"), temperature_unit),
        "temperature_max": _temperature(data.get("temperature_max"), temperature_unit),
        "temperature_trend_code": _int(data.get("temperature_trend")),
        "day_time_minutes": _int(data.get("day_time_minutes")),
        "weather_current_code": _int(data.get("weather_current")),
        "weather_next_code": _int(data.get("weather_next")),
        "current_day": _int(data.get("day")),
        "game_edition_code": _int(data.get("game_edition")),
    }
    payload.update(_implements_payload(data))
    return payload


def is_active(settings: dict) -> bool:
    module = _runtime()
    module.configure(str(settings.get("pipe_name", "fssimx")))
    return bool(module.get().get("connected"))


def shutdown() -> None:
    module = _runtime_module
    if module is not None and hasattr(module, "shutdown"):
        module.shutdown()
