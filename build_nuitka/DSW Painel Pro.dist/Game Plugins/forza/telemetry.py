from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


_runtime_module = None


def _runtime():
    global _runtime_module
    if _runtime_module is None:
        runtime_path = Path(__file__).resolve().parent / "runtime" / "forza_udp.py"
        spec = importlib.util.spec_from_file_location("forza_runtime", runtime_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Não foi possível carregar o runtime: {runtime_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _runtime_module = module
    return _runtime_module


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _speed(value_mps: float, unit: str) -> int:
    if unit == "KM/H":
        return int(round(value_mps * 3.6))
    if unit in {"MPH", "MI/H"}:
        return int(round(value_mps * 2.2369362921))
    return int(round(value_mps))


def _temperature(value_c: float, unit: str) -> float:
    if unit == "Fahrenheit":
        return round((value_c * 9.0 / 5.0) + 32.0, 1)
    return round(value_c, 1)


def _pressure(value_psi: float, unit: str) -> float:
    if unit == "BAR":
        return round(value_psi * 0.0689475729, 2)
    return round(value_psi, 2)


def _gear(raw_gear: int | None) -> int:
    # Protocolo Forza: 0 = ré, 1 = neutro, 2 = primeira, etc.
    if raw_gear is None:
        return 0
    if raw_gear in {255, -1}:
        return -1
    if raw_gear == 0:
        return -1
    if raw_gear == 1:
        return 0
    if raw_gear >= 11:
        return int(raw_gear) - 11
    return int(raw_gear) - 1


def _wheel_values(data: dict[str, Any], key: str, temperature_unit: str | None = None) -> dict[str, float]:
    values = list(data.get(key) or [0.0, 0.0, 0.0, 0.0])
    while len(values) < 4:
        values.append(0.0)
    if temperature_unit is not None:
        values = [_temperature(float(value), temperature_unit) for value in values]
    return {
        "front_left": round(float(values[0]), 4),
        "front_right": round(float(values[1]), 4),
        "rear_left": round(float(values[2]), 4),
        "rear_right": round(float(values[3]), 4),
    }


def collect(settings: dict) -> dict:
    module = _runtime()

    bind_ip = str(settings.get("telemetry_ip", settings.get("udp_ip", "0.0.0.0")))
    try:
        port = int(settings.get("telemetry_port", settings.get("udp_port", 9999)))
    except (TypeError, ValueError):
        port = 9999
    module.configure(bind_ip, port)

    data = module.get()
    speed_unit = str(settings.get("speed_unit", "KM/H"))
    pressure_unit = str(settings.get("pressure_unit", "BAR"))
    temperature_unit = str(settings.get("temperature_unit", "Celsius"))

    tire_temp = _wheel_values(data, "tire_temperature_c", temperature_unit)
    tire_slip_ratio = _wheel_values(data, "tire_slip_ratio")
    tire_slip_angle = _wheel_values(data, "tire_slip_angle")
    suspension = _wheel_values(data, "suspension_travel_m")
    wheel_speed = _wheel_values(data, "wheel_rotation_speed")
    tire_wear = _wheel_values(data, "tire_wear")

    race_on = bool(data.get("is_race_on", False))
    rpm = max(0.0, float(data.get("current_engine_rpm", 0.0) or 0.0))
    fuel = _clamp(float(data.get("fuel", 0.0) or 0.0), 0.0, 1.0)
    accel = _clamp(float(data.get("accel", 0.0) or 0.0), 0.0, 1.0)
    brake = _clamp(float(data.get("brake", 0.0) or 0.0), 0.0, 1.0)
    clutch = _clamp(float(data.get("clutch", 0.0) or 0.0), 0.0, 1.0)
    handbrake = _clamp(float(data.get("handbrake", 0.0) or 0.0), 0.0, 1.0)
    acceleration = data.get("acceleration") or [0.0, 0.0, 0.0]
    velocity = data.get("velocity") or [0.0, 0.0, 0.0]

    return {
        # Campos padrão do DSW
        "engine_rpm": int(round(rpm)),
        "current_gear": _gear(data.get("gear")),
        "speed": _speed(float(data.get("speed_mps", 0.0) or 0.0), speed_unit),
        "park_brake": handbrake > 0.01,
        "electric_enabled": race_on,
        "engine_enabled": race_on and rpm > 50.0,
        "fuel_percent": int(round(fuel * 100.0)),
        "clutch": round(clutch, 4),
        "brake": round(brake, 4),
        "throttle": round(accel, 4),
        "turbo": _pressure(float(data.get("boost_psi", 0.0) or 0.0), pressure_unit),
        "acceleration_x": round(float(acceleration[0]), 4),
        "acceleration_y": round(float(acceleration[1]), 4),
        "acceleration_z": round(float(acceleration[2]), 4),

        # Campos adicionais disponibilizados pelo protocolo Forza
        "connected": bool(data.get("connected", False)),
        "race_on": race_on,
        "packet_format": data.get("packet_format", "none"),
        "engine_max_rpm": int(round(float(data.get("engine_max_rpm", 0.0) or 0.0))),
        "engine_idle_rpm": int(round(float(data.get("engine_idle_rpm", 0.0) or 0.0))),
        "power_kw": round(float(data.get("power_w", 0.0) or 0.0) / 1000.0, 2),
        "torque_nm": round(float(data.get("torque_nm", 0.0) or 0.0), 2),
        "steering": round(float(data.get("steer", 0.0) or 0.0), 4),
        "yaw": round(float(data.get("yaw", 0.0) or 0.0), 5),
        "pitch": round(float(data.get("pitch", 0.0) or 0.0), 5),
        "roll": round(float(data.get("roll", 0.0) or 0.0), 5),
        "velocity_x": round(float(velocity[0]), 4),
        "velocity_y": round(float(velocity[1]), 4),
        "velocity_z": round(float(velocity[2]), 4),
        "lap_number": int(data.get("lap_number", 0) or 0),
        "race_position": int(data.get("race_position", 0) or 0),
        "best_lap_time": round(float(data.get("best_lap", 0.0) or 0.0), 3),
        "last_lap_time": round(float(data.get("last_lap", 0.0) or 0.0), 3),
        "current_lap_time": round(float(data.get("current_lap", 0.0) or 0.0), 3),
        "race_time": round(float(data.get("current_race_time", 0.0) or 0.0), 3),
        "distance_traveled": round(float(data.get("distance_traveled_m", 0.0) or 0.0), 2),
        "car_ordinal": int(data.get("car_ordinal", 0) or 0),
        "car_class": int(data.get("car_class", 0) or 0),
        "performance_index": int(data.get("performance_index", 0) or 0),
        "drivetrain_type": int(data.get("drivetrain_type", 0) or 0),
        "num_cylinders": int(data.get("num_cylinders", 0) or 0),
        "tire_temperature_front_left": tire_temp["front_left"],
        "tire_temperature_front_right": tire_temp["front_right"],
        "tire_temperature_rear_left": tire_temp["rear_left"],
        "tire_temperature_rear_right": tire_temp["rear_right"],
        "tire_slip_ratio_front_left": tire_slip_ratio["front_left"],
        "tire_slip_ratio_front_right": tire_slip_ratio["front_right"],
        "tire_slip_ratio_rear_left": tire_slip_ratio["rear_left"],
        "tire_slip_ratio_rear_right": tire_slip_ratio["rear_right"],
        "tire_slip_angle_front_left": tire_slip_angle["front_left"],
        "tire_slip_angle_front_right": tire_slip_angle["front_right"],
        "tire_slip_angle_rear_left": tire_slip_angle["rear_left"],
        "tire_slip_angle_rear_right": tire_slip_angle["rear_right"],
        "suspension_travel_front_left": suspension["front_left"],
        "suspension_travel_front_right": suspension["front_right"],
        "suspension_travel_rear_left": suspension["rear_left"],
        "suspension_travel_rear_right": suspension["rear_right"],
        "wheel_rotation_speed_front_left": wheel_speed["front_left"],
        "wheel_rotation_speed_front_right": wheel_speed["front_right"],
        "wheel_rotation_speed_rear_left": wheel_speed["rear_left"],
        "wheel_rotation_speed_rear_right": wheel_speed["rear_right"],
        "tire_wear_front_left": tire_wear["front_left"],
        "tire_wear_front_right": tire_wear["front_right"],
        "tire_wear_rear_left": tire_wear["rear_left"],
        "tire_wear_rear_right": tire_wear["rear_right"],
        "track_ordinal": int(data.get("track_ordinal", 0) or 0),
    }


def is_active(settings: dict) -> bool:
    module = _runtime()

    bind_ip = str(settings.get("telemetry_ip", settings.get("udp_ip", "0.0.0.0")))
    try:
        port = int(settings.get("telemetry_port", settings.get("udp_port", 9999)))
    except (TypeError, ValueError):
        port = 9999
    module.configure(bind_ip, port)
    return bool(module.get().get("connected"))


def shutdown() -> None:
    module = _runtime_module
    if module is not None and hasattr(module, "shutdown"):
        module.shutdown()
