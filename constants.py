from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelField:
    key: str
    label: str
    default: float | int | bool | str = 0


PANEL_FIELDS: tuple[PanelField, ...] = (
    PanelField("engine_rpm", "RPM"),
    PanelField("current_gear", "Current gear"),
    PanelField("speed", "Speed"),
    PanelField("water_temperature", "Water temperature"),
    PanelField("temperature_warning", "Temperature warning", False),
    PanelField("pressure", "Pressure"),
    PanelField("air_pressure_emergency", "Air Pressure emergency", False),
    PanelField("air_pressure_warning", "Air Pressure warning", False),
    PanelField("cruise_control", "Cruise Control", False),
    PanelField("wipers", "Wipers", False),
    PanelField("park_brake", "Park Brake", False),
    PanelField("motor_brake", "Motor Brake", False),
    PanelField("electric_enabled", "Electric Enabled", False),
    PanelField("engine_enabled", "Engine Enabled", False),
    PanelField("blinker_left_active", "Blinker Left Active", False),
    PanelField("blinker_right_active", "Blinker Right Active", False),
    PanelField("rotation_x", "position RX"),
    PanelField("rotation_y", "position RY"),
    PanelField("rotation_z", "position RZ"),
    PanelField("acceleration_x", "Acceleration PX"),
    PanelField("acceleration_y", "Acceleration PY"),
    PanelField("acceleration_z", "Acceleration PZ"),
    PanelField("lights_parking", "Lights Parking", False),
    PanelField("lights_low_beam", "Lights Beam Low", False),
    PanelField("lights_high_beam", "Lights Beam High", False),
    PanelField("battery_voltage_warning", "Battery Voltage Warning", False),
    PanelField("air_warning", "Air-Warning", False),
    PanelField("air_emergency", "Air-Emergency", False),
    PanelField("adblue_warning", "Adblue Warning", False),
    PanelField("oil_warning", "Oil-Warning", False),
    PanelField("water_warning", "Water-Warning", False),
    PanelField("damage_info", "damage info"),
    PanelField("mechanical_damage", "mechanical damage"),
    PanelField("vehicle_damage", "vehicle damage"),
    PanelField("fuel_percent", "FUEL (per %)"),
    PanelField("fuel_avg_consumption", "fuelAvgConsumption"),
    PanelField("clutch", "clutch"),
    PanelField("brake", "brake"),
    PanelField("throttle", "throttle"),
    PanelField("turbo", "TURBO"),
    PanelField("traction_control", "CT"),
    PanelField("abs", "ABS"),
    PanelField("oil_pressure", "OIL-Pressure"),
    PanelField("oil_temperature", "OIL temp"),
    PanelField("hazard_warning_lights", "hazard warning lights", False),
    PanelField("blinker_left_relay", "Blinker Left relay", False),
    PanelField("blinker_right_relay", "Blinker Right relay", False),
)

PANEL_FIELD_KEYS = [field.key for field in PANEL_FIELDS]
PANEL_FIELDS_BY_KEY = {field.key: field for field in PANEL_FIELDS}
PANEL_LABEL_TO_KEY = {field.label: field.key for field in PANEL_FIELDS}

DEFAULT_PANEL_ORDER = [
    "engine_rpm",
    "current_gear",
    "speed",
    "water_temperature",
    "temperature_warning",
    "pressure",
    "air_pressure_emergency",
    "air_pressure_warning",
    "cruise_control",
    "wipers",
    "park_brake",
    "motor_brake",
    "electric_enabled",
    "engine_enabled",
    "blinker_left_active",
    "blinker_right_active",
    "rotation_x",
    "rotation_y",
    "rotation_z",
    "acceleration_x",
]
