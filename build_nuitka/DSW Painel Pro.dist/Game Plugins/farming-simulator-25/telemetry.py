from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


_runtime_module = None
_IMPLEMENT_LIMIT = 10
_motion_state = {
    "initialized": False,
    "speed_mps": 0.0,
    "heading_deg": 0.0,
    "yaw_rate": 0.0,
}


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


def _lookup(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


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


def _normalize_gear(gear: Any, reverse: Any) -> int:
    normalized = _int(gear)
    if _bool(reverse) and normalized > 0:
        return -normalized
    return normalized


def _wrap_angle_delta(delta: float) -> float:
    while delta > 180.0:
        delta -= 360.0
    while delta < -180.0:
        delta += 360.0
    return delta


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _derive_motion_axes(speed_kmh: Any, heading_deg: Any, connected: bool, driving_vehicle: bool) -> dict[str, float]:
    speed_mps = max(0.0, _float(speed_kmh) / 3.6)
    heading = _float(heading_deg)

    if not connected or not driving_vehicle:
        _motion_state.update(
            {
                "initialized": False,
                "speed_mps": 0.0,
                "heading_deg": heading,
                "yaw_rate": 0.0,
            }
        )
        return {
            "rotation_x": 0.0,
            "rotation_y": round(heading, 2),
            "rotation_z": 0.0,
            "acceleration_x": 0.0,
            "acceleration_y": 0.0,
            "acceleration_z": 0.0,
        }

    if not _motion_state["initialized"]:
        _motion_state.update(
            {
                "initialized": True,
                "speed_mps": speed_mps,
                "heading_deg": heading,
                "yaw_rate": 0.0,
            }
        )
        return {
            "rotation_x": 0.0,
            "rotation_y": round(heading, 2),
            "rotation_z": 0.0,
            "acceleration_x": 0.0,
            "acceleration_y": 0.0,
            "acceleration_z": 0.0,
        }

    dt = 0.02
    previous_speed = float(_motion_state["speed_mps"])
    previous_heading = float(_motion_state["heading_deg"])
    previous_yaw_rate = float(_motion_state["yaw_rate"])

    raw_longitudinal = (speed_mps - previous_speed) / dt
    heading_delta = _wrap_angle_delta(heading - previous_heading)
    raw_yaw_rate = heading_delta / dt
    yaw_rate = (previous_yaw_rate * 0.7) + (raw_yaw_rate * 0.3)
    raw_lateral = speed_mps * yaw_rate * 0.01745329252

    # Converte aceleracoes estimadas para uma faixa amigavel ao motion do DSW.
    acceleration_x = _clamp(raw_lateral * 8.0, -100.0, 100.0)
    acceleration_y = _clamp(abs(raw_lateral) * 2.0 + abs(raw_longitudinal) * 1.2, 0.0, 100.0)
    acceleration_z = _clamp(raw_longitudinal * 7.0, -100.0, 100.0)

    _motion_state.update(
        {
            "initialized": True,
            "speed_mps": speed_mps,
            "heading_deg": heading,
            "yaw_rate": yaw_rate,
        }
    )
    return {
        "rotation_x": 0.0,
        "rotation_y": round(heading, 2),
        "rotation_z": round(yaw_rate, 2),
        "acceleration_x": round(acceleration_x, 3),
        "acceleration_y": round(acceleration_y, 3),
        "acceleration_z": round(acceleration_z, 3),
    }


def _implements_payload(data: dict[str, Any]) -> dict[str, Any]:
    positions = _list(_lookup(data, "attached_implements_position"))
    lowered = _list(_lookup(data, "attached_implements_lowered"))
    selected = _list(_lookup(data, "attached_implements_selected"))
    turned_on = _list(_lookup(data, "attached_implements_turned_on"))
    wear = _list(_lookup(data, "attached_implements_wear"))
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
    reverse_driving = _lookup(data, "is_reverse_driving")
    engine_started = _lookup(data, "is_engine_started")
    light_on = _lookup(data, "is_light_on")
    high_beam = _lookup(data, "is_light_high_on")
    beacon_on = _lookup(data, "is_light_beacon_on")

    payload = {
        "engine_rpm": _int(_lookup(data, "rpm")),
        "current_gear": _normalize_gear(_lookup(data, "gear"), reverse_driving),
        "speed": _speed(_lookup(data, "speed"), speed_unit),
        "water_temperature": _temperature(_lookup(data, "motor_temperature"), temperature_unit),
        "electric_enabled": _bool(engine_started) or _bool(light_on) or _bool(high_beam) or _bool(beacon_on),
        "engine_enabled": _bool(engine_started),
        "lights_parking": False,
        "lights_low_beam": _bool(light_on),
        "lights_high_beam": _bool(high_beam),
        "blinker_left_enabled": _bool(_lookup(data, "is_light_turn_left_enabled")),
        "blinker_right_enabled": _bool(_lookup(data, "is_light_turn_right_enabled")),
        "blinker_left_active": _bool(_lookup(data, "is_light_turn_left_on")),
        "blinker_right_active": _bool(_lookup(data, "is_light_turn_right_on")),
        "hazard_warning_lights": _bool(_lookup(data, "is_light_hazard_on")),
        "park_brake": _bool(_lookup(data, "is_hand_brake_on")),
        "fuel_percent": _ratio(_lookup(data, "fuel"), _lookup(data, "fuel_max")),
        "connected": _bool(_lookup(data, "connected")),
        "driving_vehicle": _bool(_lookup(data, "is_driving_vehicle")),
        "wear_percent": round(_float(_lookup(data, "wear")), 2),
        "operation_time_minutes": _int(_lookup(data, "operation_time_minutes")),
        "fuel_current": round(_float(_lookup(data, "fuel")), 2),
        "fuel_capacity": round(_float(_lookup(data, "fuel_max")), 2),
        "fuel_type_code": _int(_lookup(data, "fuel_type")),
        "engine_rpm_min": _int(_lookup(data, "rpm_min")),
        "engine_rpm_max": _int(_lookup(data, "rpm_max")),
        "cruise_control": _bool(_lookup(data, "is_cruise_control_on")),
        "cruise_control_speed": _int(_lookup(data, "cruise_control_speed")),
        "cruise_control_max_speed": _int(_lookup(data, "cruise_control_max_speed")),
        "ai_active": _bool(_lookup(data, "is_ai_active")),
        "reverse_driving": _bool(reverse_driving),
        "motor_fan_enabled": _bool(_lookup(data, "is_motor_fan_enabled")),
        "vehicle_price": round(_float(_lookup(data, "vehicle_price")), 2),
        "vehicle_sell_price": round(_float(_lookup(data, "vehicle_sell_price")), 2),
        "honk_on": _bool(_lookup(data, "is_honk_on")),
        "beacon_on": _bool(beacon_on),
        "hazard_on": _bool(_lookup(data, "is_light_hazard_on")),
        "wipers_on": _bool(_lookup(data, "is_wipers_on", "is_wiper_on")),
        "angle_rotation": round(_float(_lookup(data, "angle_rotation")), 2),
        "mass": round(_float(_lookup(data, "mass")), 2),
        "total_mass": round(_float(_lookup(data, "total_mass")), 2),
        "on_field": _bool(_lookup(data, "is_on_field")),
        "def_level": round(_float(_lookup(data, "def")), 2),
        "def_capacity": round(_float(_lookup(data, "def_max")), 2),
        "air_level": round(_float(_lookup(data, "air")), 2),
        "air_capacity": round(_float(_lookup(data, "air_max")), 2),
        "money": round(_float(_lookup(data, "money")), 2),
        "temperature_min": _temperature(_lookup(data, "temperature_min"), temperature_unit),
        "temperature_max": _temperature(_lookup(data, "temperature_max"), temperature_unit),
        "temperature_trend_code": _int(_lookup(data, "temperature_trend", "tempetature_trend")),
        "day_time_minutes": _int(_lookup(data, "day_time_minutes")),
        "weather_current_code": _int(_lookup(data, "weather_current")),
        "weather_next_code": _int(_lookup(data, "weather_next")),
        "current_day": _int(_lookup(data, "day")),
        "game_edition_code": _int(_lookup(data, "game_edition")),
        "_listener_error": str(_lookup(data, "_listener_error") or ""),
        "_listener_event": str(_lookup(data, "_listener_event") or ""),
    }
    payload.update(
        _derive_motion_axes(
            payload["speed"],
            payload["angle_rotation"],
            payload["connected"],
            payload["driving_vehicle"],
        )
    )
    payload.update(_implements_payload(data))
    return payload


def is_active(settings: dict) -> bool:
    module = _runtime()
    module.configure(str(settings.get("pipe_name", "fssimx")))
    peek = getattr(module, "peek", None)
    if callable(peek):
        return bool(peek().get("connected"))
    return False


def shutdown() -> None:
    module = _runtime_module
    if module is not None and hasattr(module, "shutdown"):
        module.shutdown()
