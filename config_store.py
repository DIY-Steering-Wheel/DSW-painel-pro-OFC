from __future__ import annotations

import json
import os
from pathlib import Path
import threading
from typing import Any

try:
    from .constants import DEFAULT_PANEL_ORDER, PANEL_FIELD_KEYS, PANEL_LABEL_TO_KEY
except ImportError:  # pragma: no cover
    from constants import DEFAULT_PANEL_ORDER, PANEL_FIELD_KEYS, PANEL_LABEL_TO_KEY


class ConfigStore:
    def __init__(self) -> None:
        appdata = Path(os.getenv("APPDATA", "."))
        self.base_dir = appdata / "DSW Painel Pro"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.panel_path = self.base_dir / "panel_config.json"
        self.motion_path = self.base_dir / "motion_config.json"
        self.games_path = self.base_dir / "games_installation.json"
        self.selection_path = self.base_dir / "selected_game.json"
        self.settings_path = self.base_dir / "settings.json"
        self.web_bundle_dir = self.base_dir / "web_bundle"

        self.legacy_open_source_dir = appdata / "DSW Painel Open Source"
        self.legacy_open_source_panel_path = self.legacy_open_source_dir / "panel_config.json"
        self.legacy_open_source_motion_path = self.legacy_open_source_dir / "motion_config.json"
        self.legacy_open_source_games_path = self.legacy_open_source_dir / "games_installation.json"
        self.legacy_open_source_selection_path = self.legacy_open_source_dir / "selected_game.json"
        self.legacy_open_source_settings_path = self.legacy_open_source_dir / "settings.json"

        self.legacy_dir = appdata / "DSW PAINEL PRO VARS"
        self.legacy_panel_path = self.legacy_dir / "config.json"
        self.legacy_motion_path = Path("config.json")
        self.legacy_games_path = self.legacy_dir / "games_installation.json"
        self.legacy_selection_path = self.legacy_dir / "selected_game.json"
        self._json_cache: dict[Path, tuple[int, float, Any]] = {}
        self._cache_lock = threading.Lock()

    def load_panel_config(self) -> dict[str, Any]:
        if self.panel_path.exists():
            data = self._read_json(self.panel_path)
        elif self.legacy_open_source_panel_path.exists():
            data = self._read_json(self.legacy_open_source_panel_path)
            self.save_panel_config(data)
        elif self.legacy_panel_path.exists():
            legacy = self._read_json(self.legacy_panel_path)
            data = {
                "mode": "Manual" if legacy.get("modo") == "Manual" else "Automatic",
                "port": (legacy.get("portas") or [None])[0],
                "order": [PANEL_LABEL_TO_KEY[label] for label in legacy.get("saida", []) if label in PANEL_LABEL_TO_KEY],
                "fps": 20,
            }
            self.save_panel_config(data)
        else:
            data = {"mode": "Automatic", "port": None, "order": list(DEFAULT_PANEL_ORDER), "fps": 20}
            self.save_panel_config(data)
        data["order"] = self._sanitize_order(data.get("order", DEFAULT_PANEL_ORDER))
        data["fps"] = self._sanitize_fps(data.get("fps", 20))
        return data

    def save_panel_config(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "mode": data.get("mode", "Automatic"),
            "port": data.get("port"),
            "order": self._sanitize_order(data.get("order", DEFAULT_PANEL_ORDER)),
            "fps": self._sanitize_fps(data.get("fps", 20)),
        }
        self._write_json(self.panel_path, payload)
        return payload

    def load_motion_config(self) -> dict[str, Any]:
        default = {
            "port": None,
            "baudrate": 115200,
            "fps": 20,
            "is_sending": False,
            "phase_invert_x": False,
            "phase_invert_y": False,
            "phase_invert_z": False,
            "onoff_invert_x": True,
            "onoff_invert_y": True,
            "onoff_invert_z": True,
            "offset_power_x": 0.0,
            "offset_power_y": 0.0,
            "offset_power_z": 0.0,
            "min_value": -100.0,
            "max_value": 100.0,
        }
        if self.motion_path.exists():
            data = self._read_json(self.motion_path)
        elif self.legacy_open_source_motion_path.exists():
            data = self._read_json(self.legacy_open_source_motion_path)
            self.save_motion_config(data)
        elif self.legacy_motion_path.exists():
            data = self._read_json(self.legacy_motion_path)
            self.save_motion_config(data)
        else:
            data = {}
            self.save_motion_config(default)
        merged = dict(default)
        merged.update(data)
        merged["fps"] = self._sanitize_fps(merged.get("fps", 20))
        return merged

    def save_motion_config(self, data: dict[str, Any]) -> dict[str, Any]:
        current = self.load_motion_config() if self.motion_path.exists() else {
            "port": None,
            "baudrate": 115200,
            "fps": 20,
            "is_sending": False,
            "phase_invert_x": False,
            "phase_invert_y": False,
            "phase_invert_z": False,
            "onoff_invert_x": True,
            "onoff_invert_y": True,
            "onoff_invert_z": True,
            "offset_power_x": 0.0,
            "offset_power_y": 0.0,
            "offset_power_z": 0.0,
            "min_value": -100.0,
            "max_value": 100.0,
        }
        current.update(data)
        current["fps"] = self._sanitize_fps(current.get("fps", 20))
        self._write_json(self.motion_path, current)
        return current

    def load_games(self, game_names: list[str]) -> dict[str, str]:
        if self.games_path.exists():
            data = self._read_json(self.games_path)
        elif self.legacy_open_source_games_path.exists():
            data = self._read_json(self.legacy_open_source_games_path)
            self._write_json(self.games_path, data)
        elif self.legacy_games_path.exists():
            data = self._read_json(self.legacy_games_path)
            self._write_json(self.games_path, data)
        else:
            data = {name: "no" for name in game_names}
            self._write_json(self.games_path, data)
        for name in game_names:
            data.setdefault(name, "no")
        return data

    def save_games(self, games: dict[str, str]) -> dict[str, str]:
        self._write_json(self.games_path, games)
        return games

    def load_selected_game(self, default_name: str) -> str:
        if self.selection_path.exists():
            return self._read_json(self.selection_path).get("selected_game", default_name)
        if self.legacy_open_source_selection_path.exists():
            selected = self._read_json(self.legacy_open_source_selection_path).get("selected_game", default_name)
            self.save_selected_game(selected)
            return selected
        if self.legacy_selection_path.exists():
            selected = self._read_json(self.legacy_selection_path).get("selected_game", default_name)
            self.save_selected_game(selected)
            return selected
        self.save_selected_game(default_name)
        return default_name

    def save_selected_game(self, game_name: str) -> None:
        self._write_json(self.selection_path, {"selected_game": game_name})

    def load_settings(self) -> dict[str, Any]:
        default = {
            "auto_start_enabled": False,
            "detect_open_game_on_start": False,
            "launch_with_windows": False,
            "minimize_to_tray": True,
            "speed_unit": "KM/H",
            "pressure_unit": "BAR",
            "temperature_unit": "Celsius",
            "fallback_overrides": {},
            "value_equalization_rules": [],
            "web_server": {
                "http_enabled": False,
                "http_auto_start": False,
                "http_host": "0.0.0.0",
                "http_port": 8080,
                "bundle_path": "",
                "bundle_root": "",
                "selected_template": "simple-dashboard",
                "udp_enabled": False,
                "udp_auto_start": False,
                "udp_host": "0.0.0.0",
                "udp_port": 28000,
            },
        }
        if self.settings_path.exists():
            data = self._read_json(self.settings_path)
            default.update(data)
        elif self.legacy_open_source_settings_path.exists():
            data = self._read_json(self.legacy_open_source_settings_path)
            default.update(data)
            self._write_json(self.settings_path, default)
        else:
            self._write_json(self.settings_path, default)
        if not isinstance(default.get("fallback_overrides"), dict):
            default["fallback_overrides"] = {}
        default["value_equalization_rules"] = self._sanitize_value_equalization(default.get("value_equalization_rules"))
        if not isinstance(default.get("web_server"), dict):
            default["web_server"] = {}
        default["web_server"] = self._merge_web_server_defaults(default["web_server"])
        return default

    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        current = self.load_settings()
        current.update(data)
        current["value_equalization_rules"] = self._sanitize_value_equalization(current.get("value_equalization_rules"))
        current["web_server"] = self._merge_web_server_defaults(current.get("web_server", {}))
        self._write_json(self.settings_path, current)
        return current

    def _merge_web_server_defaults(self, data: dict[str, Any]) -> dict[str, Any]:
        default = {
            "http_enabled": False,
            "http_auto_start": False,
            "http_host": "0.0.0.0",
            "http_port": 8080,
            "bundle_path": "",
            "bundle_root": "",
            "selected_template": "simple-dashboard",
            "udp_enabled": False,
            "udp_auto_start": False,
            "udp_host": "0.0.0.0",
            "udp_port": 28000,
        }
        merged = dict(default)
        merged.update(data or {})
        return merged

    def _sanitize_order(self, order: list[str]) -> list[str]:
        valid = [item for item in order if item in PANEL_FIELD_KEYS]
        if not valid:
            return list(DEFAULT_PANEL_ORDER)
        if len(valid) >= 20:
            return valid[:20]
        filled = list(valid)
        fallback_index = 0
        while len(filled) < 20:
            filled.append(DEFAULT_PANEL_ORDER[fallback_index % len(DEFAULT_PANEL_ORDER)])
            fallback_index += 1
        return filled

    def _sanitize_fps(self, value: Any) -> int:
        try:
            fps = int(value)
        except (TypeError, ValueError):
            fps = 20
        return max(1, min(fps, 120))

    def _sanitize_value_equalization(self, rules: Any) -> list[dict[str, Any]]:
        if not isinstance(rules, list):
            return []

        sanitized: list[dict[str, Any]] = []
        for rule in rules:
            if not isinstance(rule, dict):
                continue

            field_key = str(rule.get("field_key", "")).strip()
            if field_key not in PANEL_FIELD_KEYS:
                continue

            source_min = self._coerce_number(rule.get("source_min"))
            source_max = self._coerce_number(rule.get("source_max"))
            target_min = self._coerce_number(rule.get("target_min"))
            target_max = self._coerce_number(rule.get("target_max"))
            if None in {source_min, source_max, target_min, target_max}:
                continue

            game_ids = []
            for game_id in rule.get("game_ids", []):
                text = str(game_id).strip()
                if text and text not in game_ids:
                    game_ids.append(text)

            sanitized.append(
                {
                    "field_key": field_key,
                    "source_min": source_min,
                    "source_max": source_max,
                    "target_min": target_min,
                    "target_max": target_max,
                    "apply_to_all": bool(rule.get("apply_to_all", False)),
                    "game_ids": game_ids,
                }
            )

        return sanitized

    def _read_json(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        cache_key = path.resolve()
        signature = (stat.st_size, stat.st_mtime)
        with self._cache_lock:
            cached = self._json_cache.get(cache_key)
            if cached and cached[:2] == signature:
                cached_value = cached[2]
                if isinstance(cached_value, dict):
                    return dict(cached_value)
                return cached_value

        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        with self._cache_lock:
            self._json_cache[cache_key] = (signature[0], signature[1], data)

        if isinstance(data, dict):
            return dict(data)
        return data

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        stat = path.stat()
        cache_key = path.resolve()
        with self._cache_lock:
            self._json_cache[cache_key] = (stat.st_size, stat.st_mtime, payload)

    def _coerce_number(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
