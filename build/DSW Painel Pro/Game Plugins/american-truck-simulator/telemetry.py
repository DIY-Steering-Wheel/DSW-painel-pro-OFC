from __future__ import annotations

import importlib.util
from pathlib import Path


_runtime_module = None


def _runtime():
    global _runtime_module
    if _runtime_module is None:
        runtime_path = Path(__file__).resolve().parent / "runtime" / "atssdkclient.py"
        spec = importlib.util.spec_from_file_location("ats_runtime", runtime_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        _runtime_module = module
    return _runtime_module


def collect(settings: dict) -> dict:
    module = _runtime()
    e = module.atssdkclient()
    e.update()
    speed = int(e.speed * 3.6 if settings["speed_unit"] == "KM/H" else e.speed * 2.236936)
    fuel_percent = int((e.fuel / e.fuelCapacity) * 100) if e.fuelCapacity else 0
    water_temperature = int(e.waterTemperature)
    if settings["temperature_unit"] != "Celsius":
        water_temperature = int((water_temperature * 9 / 5) + 32)
    pressure = float(e.airPressure)
    if settings["pressure_unit"] == "BAR":
        pressure /= 14.5038
    return {
        "engine_rpm": int(e.engineRpm),
        "current_gear": e.gearDashboard,
        "speed": speed,
        "water_temperature": water_temperature,
        "temperature_warning": e.WaterTemperatureWarning,
        "pressure": round(pressure, 2),
        "air_pressure_emergency": e.AirPressureEmergency,
        "air_pressure_warning": e.AirPressureWarning,
        "cruise_control": e.CruiseControl,
        "wipers": e.Wipers,
        "park_brake": e.ParkBrake,
        "motor_brake": e.MotorBrake,
        "electric_enabled": e.ElectricEnabled,
        "engine_enabled": e.EngineEnabled,
        "blinker_left_active": e.BlinkerLeftActive,
        "blinker_right_active": e.BlinkerRightActive,
        "rotation_x": e.rotationX,
        "rotation_y": e.rotationY,
        "rotation_z": e.rotationZ,
        "acceleration_x": e.accelerationX,
        "acceleration_y": e.accelerationY,
        "acceleration_z": e.accelerationZ,
        "lights_parking": e.LightsParking,
        "lights_low_beam": e.LightsBeamLow,
        "lights_high_beam": e.LightsBeamHigh,
        "battery_voltage_warning": e.BatteryVoltageWarning,
        "air_warning": e.AirPressureWarning,
        "air_emergency": e.AirPressureEmergency,
        "adblue_warning": e.AdblueWarning,
        "oil_warning": e.OilPressureWarning,
        "water_warning": e.WaterTemperatureWarning,
        "damage_info": ((e.wearEngine + e.wearTransmission + e.wearChassis + e.wearCabin) / 4),
        "mechanical_damage": ((e.wearEngine + e.wearTransmission) / 2),
        "vehicle_damage": ((e.wearChassis + e.wearCabin) / 2),
        "fuel_percent": fuel_percent,
        "fuel_avg_consumption": f"{e.fuelAvgConsumption:.2f}",
        "hazard_warning_lights": bool(e.BlinkerLeftOn and e.BlinkerRightOn),
        "blinker_left_relay": e.BlinkerLeftOn,
        "blinker_right_relay": e.BlinkerRightOn,
    }
