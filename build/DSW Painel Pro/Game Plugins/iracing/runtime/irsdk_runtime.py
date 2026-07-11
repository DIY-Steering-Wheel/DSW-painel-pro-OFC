from __future__ import annotations

import threading
import time
from typing import Any


_lock = threading.Lock()
_state: dict[str, Any] = {"connected": False}
_sdk = None
_sdk_missing = False
_last_init_attempt = 0.0
_sdk_backend = ""


def _load_sdk():
    global _sdk, _sdk_missing, _last_init_attempt, _sdk_backend
    if _sdk is not None or _sdk_missing:
        return
    now = time.time()
    if now - _last_init_attempt < 2.0:
        return
    _last_init_attempt = now
    candidates = (
        ("irsdk", "IRSDK"),
        ("pyirsdk", "IRSDK"),
    )
    for module_name, class_name in candidates:
        try:
            module = __import__(module_name, fromlist=[class_name])
            sdk_class = getattr(module, class_name)
            sdk = sdk_class()
            sdk.startup()
            _sdk = sdk
            _sdk_backend = module_name
            _sdk_missing = False
            return
        except Exception:
            _sdk = None
    _sdk_missing = True


def _value(name: str, default: Any = 0) -> Any:
    sdk = _sdk
    if sdk is None:
        return default
    try:
        return sdk[name]
    except Exception:
        try:
            return sdk.get(name, default)
        except Exception:
            return default


def get() -> dict[str, Any]:
    _load_sdk()
    sdk = _sdk
    if sdk is None:
        return {
            "connected": False,
            "sdk_available": False,
            "sdk_backend": _sdk_backend,
        }
    try:
        connected = bool(getattr(sdk, "is_initialized", False)) and bool(getattr(sdk, "is_connected", False))
    except Exception:
        connected = False
    if not connected:
        return {
            "connected": False,
            "sdk_available": True,
            "sdk_backend": _sdk_backend,
        }

    payload = {
        "connected": True,
        "sdk_available": True,
        "sdk_backend": _sdk_backend,
        "rpm": _value("RPM", 0),
        "gear": _value("Gear", 0),
        "speed": _value("Speed", 0.0),
        "water_temp": _value("WaterTemp", 0.0),
        "fuel_level": _value("FuelLevel", 0.0),
        "fuel_pct": _value("FuelLevelPct", 0.0),
        "clutch": _value("Clutch", 0.0),
        "brake": _value("Brake", 0.0),
        "throttle": _value("Throttle", 0.0),
        "lat_accel": _value("LatAccel", 0.0),
        "long_accel": _value("LongAccel", 0.0),
        "vert_accel": _value("VertAccel", 0.0),
        "oil_temp": _value("OilTemp", 0.0),
        "oil_press": _value("OilPress", 0.0),
        "lap": _value("Lap", 0),
        "lap_best": _value("LapBestLapTime", 0.0),
        "lap_last": _value("LapLastLapTime", 0.0),
        "lap_current": _value("LapCurrentLapTime", 0.0),
        "position": _value("PlayerCarPosition", 0),
        "on_pit_road": _value("OnPitRoad", False),
    }
    with _lock:
        _state.clear()
        _state.update(payload)
        return dict(_state)


def shutdown() -> None:
    global _sdk
    sdk = _sdk
    if sdk is not None:
        try:
            sdk.shutdown()
        except Exception:
            pass
    _sdk = None
