from __future__ import annotations

import os
import json
import sys
import threading
import time
import webbrowser
from collections import deque
from pathlib import Path
from typing import Any

import psutil

FARM_RECONNECT_GRACE_SECONDS = 5.5


def _escape_vbs_string(value: str) -> str:
    return str(value).replace('"', '""')


def _quote_vbs_command_part(value: str) -> str:
    text = str(value)
    if not text:
        return '""'
    if any(char.isspace() for char in text) or '"' in text:
        return f'"{text.replace(chr(34), chr(34) * 2)}"'
    return text

try:
    from .adjacent_devices import AdjacentDevicesManager
    from .config_store import ConfigStore
    from .constants import PANEL_FIELDS, panel_field_description
    from .installers import InstallerService
    from .plugin_registry import PluginRegistry
    from .runtime_paths import get_app_base_dir
    from .serial_services import MotionSender, PanelSender, build_telemetry_rows
    from .telemetry_shared_memory import TelemetrySharedMemoryService
    from .web_runtime import WebRuntimeService
except ImportError:  # pragma: no cover
    from adjacent_devices import AdjacentDevicesManager
    from config_store import ConfigStore
    from constants import PANEL_FIELDS, panel_field_description
    from installers import InstallerService
    from plugin_registry import PluginRegistry
    from runtime_paths import get_app_base_dir
    from serial_services import MotionSender, PanelSender, build_telemetry_rows
    from telemetry_shared_memory import TelemetrySharedMemoryService
    from web_runtime import WebRuntimeService


class TelemetryBridge:
    def __init__(self) -> None:
        self.base_dir = get_app_base_dir()
        self.store = ConfigStore()
        self.registry = PluginRegistry(self.base_dir)
        self.panel_sender = PanelSender(self.store)
        self.motion_sender = MotionSender(self.store)
        self.adjacent_devices = AdjacentDevicesManager(self.store)
        self.telemetry_share = TelemetrySharedMemoryService()
        self.installer = InstallerService(self.base_dir, self.registry)
        self.web_runtime = WebRuntimeService(self.store, self.api_payload)
        self.plugins = self.registry.load_plugins()
        self._plugin_by_name = {plugin["name"]: plugin for plugin in self.plugins}

        settings = self.store.load_settings()
        self.speed_unit = settings["speed_unit"]
        self.pressure_unit = settings["pressure_unit"]
        self.temperature_unit = settings["temperature_unit"]

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._collector_module = None
        self._stop_event = threading.Event()
        self._collector_session = 0
        self._selected_game = self._resolve_selected_game_name(self.store.load_selected_game(self.plugins[0]["name"]))
        self._save_selected_game_safe(self._selected_game)
        self._installed_games = self.store.load_games(list(self._plugin_by_name))
        self._settings = settings
        self._is_collecting = False
        self._status_text = self._status_for_game(self._selected_game)
        self._telemetry: dict[str, Any] = {}
        self._last_error = ""
        self._install_folder = ""
        self._plugin_package_path = ""
        self._plugin_github_url = ""
        self._plugin_github_release_data: dict[str, Any] = {"repo_url": "", "repo_name": "", "releases": []}
        self._template_package_path = ""
        self._ui_messages: deque[dict[str, Any]] = deque(maxlen=20)
        self._message_seq = 0
        self._about_template_html = self._load_about_template()
        self._last_active_telemetry: dict[str, Any] = {}
        self._last_active_telemetry_at = 0.0
        self._apply_windows_startup(bool(settings.get("launch_with_windows", False)))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            selected = self._selected_game
            collecting = self._is_collecting
            status_text = self._status_text
            telemetry = dict(self._telemetry)
            last_error = self._last_error
            install_folder = self._install_folder
            plugin_package_path = self._plugin_package_path
            plugin_github_url = self._plugin_github_url
            plugin_github_release_data = dict(self._plugin_github_release_data)
            template_package_path = self._template_package_path
            settings = dict(self._settings)
            messages = list(self._ui_messages)

        selected_plugin = self.plugin_meta(selected)
        emitted_fields = self._visible_fields_for_plugin(selected_plugin, telemetry)
        installed_games = self.store.load_games(list(self._plugin_by_name))
        panel_status = self.panel_sender.status(collecting)
        motion_status = self.motion_sender.status(collecting)
        panel_status["kind"] = "panel"
        motion_status["kind"] = "motion"
        adjacent_status = self.adjacent_devices.status_list(collecting)
        active_process_names = self._active_process_names()

        games = []
        for plugin in self.plugins:
            game_name = plugin["name"]
            installed = "yes" if not plugin["requires_install"] else installed_games.get(game_name, "no")
            games.append(
                {
                    "id": plugin["id"],
                    "name": game_name,
                    "icon": plugin["icon"],
                    "requires_install": plugin["requires_install"],
                    "installed": installed,
                    "is_active_process": self.is_game_active(game_name, active_process_names),
                    "selected": game_name == selected,
                }
            )

        return {
            "games": games,
            "selected_game": selected,
            "is_collecting": collecting,
            "status_text": status_text,
            "telemetry_rows": build_telemetry_rows(telemetry, emitted_fields),
            "last_error": last_error,
            "messages": messages,
            "footer": {"auto_start_enabled": bool(settings.get("auto_start_enabled", False))},
            "panel_config": self.store.load_panel_config(),
            "panel_fields": [
                {
                    "key": field.key,
                    "label": field.label,
                    "default": field.default,
                    "description": panel_field_description(field.key, field.label),
                }
                for field in PANEL_FIELDS
            ],
            "motion_config": self.store.load_motion_config(),
            "motion_preview": self.motion_sender.preview(telemetry),
            "basic_settings": settings,
            "adjacent_device_presets": self.adjacent_devices.preset_catalog(),
            "adjacent_device_encodings": self.adjacent_devices.encoding_catalog(),
            "available_ports": self.panel_sender.list_ports(),
            "device_status": {
                "panel": panel_status,
                "motion": motion_status,
                "adjacent": adjacent_status,
            },
            "install_modal": {
                "selected_folder": install_folder,
                "plugin": selected_plugin,
                "installed": (not selected_plugin["requires_install"]) or installed_games.get(selected, "no") == "yes",
            },
            "plugin_manager": {
                "selected_package": plugin_package_path,
                "github_repo_url": plugin_github_url,
                "github_release_data": plugin_github_release_data,
                "plugins": [
                    {
                        "id": plugin["id"],
                        "name": plugin["name"],
                        "built_in": bool(plugin.get("built_in", False)),
                        "requires_install": bool(plugin.get("requires_install", False)),
                    }
                    for plugin in self.plugins
                ],
            },
            "template_manager": {
                "selected_package": template_package_path,
            },
            "about_info": {
                "owner_name": "Valdemir",
                "owner_team": "equipe DSW de Simuladores",
                "discord_url": "#",
                "discord_label": "Discord oficial da DSW",
                "project_status": "Projeto mantido por Valdemir e pela DSW",
                "pix_key": "ece64ef9-cee3-4c39-8631-bdac226c7563",
                "donation_message": "Se quiser apoiar o desenvolvimento do projeto, voce pode usar este QR Code Pix para doacao.",
                "template_html": self._about_template_html,
                "donation_qr_data_url": self.web_runtime.build_pix_donation_qr(
                    "ece64ef9-cee3-4c39-8631-bdac226c7563",
                    name="DSW SIMULADORES",
                    city="BRASIL",
                ),
            },
            "web_server": self.web_runtime.status(),
            "telemetry_share": self.telemetry_share.status(),
        }

    def api_payload(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        telemetry_map = {row["key"]: row["value"] for row in snapshot["telemetry_rows"]}
        snapshot["panel_preview"] = {
            "ordered_values": self.panel_sender.preview_values(telemetry_map),
            "configured_order": snapshot["panel_config"]["order"],
        }
        return snapshot

    def refresh_games(self) -> dict[str, Any]:
        self._reload_plugins()
        with self._lock:
            self._installed_games = self.store.load_games(list(self._plugin_by_name))
            self._settings = self.store.load_settings()
            self.speed_unit = self._settings["speed_unit"]
            self.pressure_unit = self._settings["pressure_unit"]
            self.temperature_unit = self._settings["temperature_unit"]
            if not self._is_collecting:
                self._status_text = self._status_for_game(self._selected_game)
        return self.snapshot()

    def auto_manage_active_game(self) -> dict[str, Any]:
        self.refresh_games()
        settings = self.store.load_settings()
        detect_enabled = bool(settings.get("detect_open_game_on_start"))
        if not detect_enabled:
            return self.snapshot()

        selected = self.snapshot()["selected_game"]
        is_collecting = self.snapshot()["is_collecting"]
        selected_active = self.is_game_active(selected)
        active_game = self._find_first_active_game()

        if is_collecting and selected_active:
            return self.snapshot()

        if is_collecting and not selected_active:
            self.stop_collection(wait=True)

        if active_game is None:
            return self.snapshot()

        plugin = self.plugin_meta(active_game)
        installed = "yes" if not plugin["requires_install"] else self.store.load_games(list(self._plugin_by_name)).get(active_game, "no")

        with self._lock:
            changed_game = self._selected_game != active_game
            if changed_game:
                self._selected_game = active_game
                self._save_selected_game_safe(active_game)
            if not self._is_collecting:
                self._status_text = self._status_for_game(active_game)
                self._last_error = ""

        if installed == "yes" and not self.snapshot()["is_collecting"]:
            self.start_collection()
            if changed_game:
                self._push_message("success", "Troca automatica", f"{active_game} foi detectado e iniciado automaticamente.")
        elif changed_game:
            self._push_message("success", "Troca automatica", f"{active_game} foi detectado automaticamente.")

        return self.snapshot()

    def auto_select_active_game(self) -> dict[str, Any]:
        active_game = self._find_first_active_game()
        if active_game is not None:
            return self.select_game(active_game)
        return self.snapshot()

    def select_game(self, game_name: str) -> dict[str, Any]:
        blocked = False
        with self._lock:
            if self._is_collecting:
                self._set_error_locked("Pare a coleta antes de trocar de jogo.")
                blocked = True
            else:
                self._selected_game = game_name
                self._save_selected_game_safe(game_name)
                self._status_text = self._status_for_game(game_name)
                self._last_error = ""
        if blocked:
            return self.snapshot()
        return self.snapshot()

    def toggle_selected_game(self) -> dict[str, Any]:
        selected = self.snapshot()["selected_game"]
        plugin = self.plugin_meta(selected)
        installed = "yes" if not plugin["requires_install"] else self.store.load_games(list(self._plugin_by_name)).get(selected, "no")
        if installed == "no":
            return self.snapshot()
        if self.snapshot()["is_collecting"]:
            self.stop_collection()
        else:
            self.start_collection()
        return self.snapshot()

    def install_selected_game(self) -> dict[str, Any]:
        selected = self.snapshot()["selected_game"]
        data = self.store.load_games(list(self._plugin_by_name))
        data[selected] = "yes"
        self.store.save_games(data)
        self._set_status("Pronto para coletar")
        return self.refresh_games()

    def uninstall_selected_game(self) -> dict[str, Any]:
        selected = self.snapshot()["selected_game"]
        plugin = self.plugin_meta(selected)
        folder = self.snapshot()["install_modal"]["selected_folder"]
        if plugin["requires_install"] and not folder:
            self._set_error("Selecione a pasta do jogo antes de remover a integracao.")
            return self.snapshot()
        try:
            module = self.registry.load_module(plugin, "installer_script")
            if module is not None and hasattr(module, "uninstall"):
                message = module.uninstall(folder, Path(plugin["plugin_dir"]))
            else:
                message = f"Integração removida de {selected}."
            games = self.store.load_games(list(self._plugin_by_name))
            games[selected] = "no"
            self.store.save_games(games)
            self._set_status(message)
            self._push_message("success", "Remoção concluída", message)
        except Exception as exc:
            self._set_error(f"Falha ao remover integração: {exc}")
        return self.snapshot()

    def plugin_meta(self, game_name: str) -> dict[str, Any]:
        resolved_name = self._resolve_selected_game_name(game_name)
        return self._plugin_by_name[resolved_name]

    def set_auto_start(self, enabled: bool) -> dict[str, Any]:
        with self._lock:
            self._settings = self.store.save_settings({"auto_start_enabled": bool(enabled)})
        return self.snapshot()

    def save_basic_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        if "adjacent_devices" in data:
            self.adjacent_devices.validate_configs(data.get("adjacent_devices") or [])
        with self._lock:
            self._settings = self.store.save_settings(data)
            self.speed_unit = self._settings["speed_unit"]
            self.pressure_unit = self._settings["pressure_unit"]
            self.temperature_unit = self._settings["temperature_unit"]
        self._apply_windows_startup(bool(self._settings.get("launch_with_windows", False)))
        return self.snapshot()

    def apply_selected_game_unit_defaults(self) -> dict[str, Any]:
        plugin = self.plugin_meta(self.snapshot()["selected_game"])
        preferred = plugin.get("preferred_units") or plugin.get("emitted_units") or {}
        payload = {}
        if preferred.get("speed") in {"KM/H", "MPH"}:
            payload["speed_unit"] = preferred["speed"]
        if preferred.get("pressure") in {"BAR", "PSI"}:
            payload["pressure_unit"] = preferred["pressure"]
        if preferred.get("temperature") in {"Celsius", "Fahrenheit"}:
            payload["temperature_unit"] = preferred["temperature"]
        if not payload:
            return self.snapshot()
        return self.save_basic_settings(payload)

    def save_panel_config(self, data: dict[str, Any]) -> dict[str, Any]:
        self.store.save_panel_config(data)
        return self.snapshot()

    def save_motion_config(self, data: dict[str, Any]) -> dict[str, Any]:
        self.store.save_motion_config(data)
        return self.snapshot()

    def export_panel_config_json(self) -> str:
        return json.dumps(self.store.load_panel_config(), ensure_ascii=False, indent=2)

    def import_panel_config_json(self, text: str) -> dict[str, Any]:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise RuntimeError("Arquivo JSON invalido para config do painel.")
        self.store.save_panel_config(data)
        self._push_message("success", "Painel importado", "Configuracao do painel carregada do JSON.")
        return self.snapshot()

    def send_device_command(self, device_type: str, command: str) -> dict[str, Any]:
        try:
            text = str(command or "")
            if not text.strip():
                raise RuntimeError("Digite um comando antes de enviar.")
            if device_type == "panel":
                self.panel_sender.send_command(text)
                device_label = "Painel"
            elif device_type == "motion":
                self.motion_sender.send_command(text)
                device_label = "Motion"
            elif device_type.startswith("adjacent:"):
                slot_index = int(device_type.split(":", 1)[1]) - 1
                self.adjacent_devices.send_command(slot_index, text)
                device_label = f"Adjacente {slot_index + 1}"
            else:
                raise RuntimeError("Dispositivo serial desconhecido.")
            self._set_status(f"Comando enviado para {device_label.lower()}.")
            self._push_message("success", "Comando enviado", f"{device_label}: {text}")
        except Exception as exc:
            self._set_error(f"Falha ao enviar comando serial: {exc}")
        return self.snapshot()

    def open_external_url(self, url: str) -> bool:
        try:
            return bool(webbrowser.open(url))
        except Exception:
            return False

    def set_install_folder(self, folder: str) -> dict[str, Any]:
        with self._lock:
            self._install_folder = folder
        return self.snapshot()

    def set_plugin_package_path(self, package_path: str) -> dict[str, Any]:
        with self._lock:
            self._plugin_package_path = package_path
        return self.snapshot()

    def set_plugin_github_url(self, repo_url: str) -> dict[str, Any]:
        with self._lock:
            self._plugin_github_url = (repo_url or "").strip()
        return self.snapshot()

    def set_template_package_path(self, package_path: str) -> dict[str, Any]:
        with self._lock:
            self._template_package_path = package_path
        return self.snapshot()

    def save_web_server_config(self, data: dict[str, Any]) -> dict[str, Any]:
        current_status = self.web_runtime.status()
        current_template = current_status.get("selected_template")
        incoming_template = data.get("selected_template", current_template)
        if current_status.get("http_enabled") and incoming_template != current_template:
            raise RuntimeError("Servidor ligado, desligue para depois alterar o template HTML.")
        self.web_runtime.save_config(data)
        return self.snapshot()

    def preview_adjacent_device(self, config: dict[str, Any]) -> dict[str, Any]:
        slot_index = max(0, min(int(config.get("slot", 1)) - 1, 3))
        telemetry = self._latest_telemetry_for_preview()
        with self._lock:
            selected_game = self._selected_game
            is_collecting = self._is_collecting
        preview = self.adjacent_devices.preview_config(slot_index, config, telemetry)
        preview["selected_game"] = selected_game
        preview["telemetry_source"] = "live" if is_collecting and telemetry else "cache"
        return preview

    def ensure_background_services_started(self) -> dict[str, Any]:
        config = self.store.load_settings().get("web_server", {})
        if config.get("http_auto_start"):
            try:
                self.web_runtime.start_http()
            except Exception as exc:
                self._set_error(str(exc))
        if config.get("udp_auto_start"):
            try:
                self.web_runtime.start_udp()
            except Exception as exc:
                self._set_error(str(exc))
        return self.snapshot()

    def import_template_package(self) -> dict[str, Any]:
        try:
            package_path = self.snapshot()["template_manager"]["selected_package"]
            imported_names = self.web_runtime.import_template_archive(package_path)
            with self._lock:
                self._template_package_path = ""
            imported_templates = self.web_runtime.load_template_catalog()
            if imported_names and not self.web_runtime.status().get("http_enabled"):
                imported = next((item for item in imported_templates if item["name"] == imported_names[0]), None)
                if imported is not None:
                    self.web_runtime.save_config({"selected_template": imported["id"]})
            message = ", ".join(imported_names)
            self._set_status(f"Template importado: {message}")
            self._push_message("success", "Template importado", message)
        except Exception as exc:
            self._set_error(f"Falha ao importar template: {exc}")
        return self.snapshot()

    def delete_template(self, template_id: str) -> dict[str, Any]:
        try:
            if self.web_runtime.status().get("http_enabled"):
                raise RuntimeError("Servidor ligado, desligue para depois alterar os templates HTML.")
            removed_name = self.web_runtime.delete_template(template_id)
            self._set_status(f"Template removido: {removed_name}")
            self._push_message("success", "Template removido", removed_name)
        except Exception as exc:
            self._set_error(f"Falha ao remover template: {exc}")
        return self.snapshot()

    def start_web_server(self) -> dict[str, Any]:
        try:
            self.web_runtime.start_http()
            with self._lock:
                self._last_error = ""
                self._status_text = "Servidor web iniciado."
        except Exception as exc:
            self._set_error(str(exc))
        return self.snapshot()

    def stop_web_server(self) -> dict[str, Any]:
        self.web_runtime.stop_http()
        return self.snapshot()

    def start_udp_server(self) -> dict[str, Any]:
        try:
            self.web_runtime.start_udp()
            with self._lock:
                self._last_error = ""
                self._status_text = "Servidor UDP iniciado."
        except Exception as exc:
            self._set_error(str(exc))
        return self.snapshot()

    def stop_udp_server(self) -> dict[str, Any]:
        self.web_runtime.stop_udp()
        return self.snapshot()

    def import_plugin_package(self) -> dict[str, Any]:
        try:
            package_path = self.snapshot()["plugin_manager"]["selected_package"]
            imported_names = self.registry.import_package(package_path)
            self._reload_plugins()
            games = self.store.load_games(list(self._plugin_by_name))
            for plugin_name in self._plugin_by_name:
                games.setdefault(plugin_name, "no")
            self.store.save_games(games)
            with self._lock:
                self._plugin_package_path = ""
                self._last_error = ""
                self._status_text = f"Plugin importado: {', '.join(imported_names)}"
                if imported_names:
                    self._selected_game = imported_names[0]
                    self._save_selected_game_safe(self._selected_game)
            self._push_message("success", "Plugin importado", ", ".join(imported_names))
        except Exception as exc:
            self._set_error(f"Falha ao importar plugin: {exc}")
        return self.snapshot()

    def fetch_plugin_github_releases(self) -> dict[str, Any]:
        try:
            repo_url = self.snapshot()["plugin_manager"]["github_repo_url"]
            release_data = self.registry.fetch_github_releases(repo_url)
            with self._lock:
                self._plugin_github_release_data = release_data
                self._last_error = ""
            release_count = len(release_data.get("releases", []))
            self._push_message("success", "GitHub conectado", f"{release_count} releases carregados de {release_data['repo_name']}.")
        except Exception as exc:
            with self._lock:
                self._plugin_github_release_data = {"repo_url": "", "repo_name": "", "releases": []}
            self._set_error(f"Falha ao consultar releases: {exc}")
        return self.snapshot()

    def clear_plugin_github_releases(self) -> dict[str, Any]:
        with self._lock:
            self._plugin_github_release_data = {"repo_url": "", "repo_name": "", "releases": []}
        return self.snapshot()

    def download_plugin_release_asset(self, download_url: str, asset_name: str, action: str) -> dict[str, Any]:
        try:
            result = self.registry.download_release_asset(download_url, asset_name, action)
            downloaded_path = result.get("path", "")
            with self._lock:
                if action == "download":
                    self._plugin_package_path = downloaded_path
                self._last_error = ""
            if action == "import":
                self._reload_plugins()
                games = self.store.load_games(list(self._plugin_by_name))
                for plugin_name in self._plugin_by_name:
                    games.setdefault(plugin_name, "no")
                self.store.save_games(games)
                imported_names = result.get("imported_names", [])
                with self._lock:
                    if imported_names:
                        self._selected_game = imported_names[0]
                        self._save_selected_game_safe(self._selected_game)
                message = ", ".join(imported_names) if imported_names else asset_name
                self._set_status(f"Plugin importado: {message}")
                self._push_message("success", "Plugin importado do GitHub", message)
            elif action == "extract":
                self._set_status(f"Arquivo extraido: {result.get('extract_dir', '')}")
                self._push_message("success", "Arquivo extraido", result.get("extract_dir", downloaded_path))
            else:
                self._set_status(f"Arquivo baixado: {Path(downloaded_path).name}")
                self._push_message("success", "Download concluido", downloaded_path)
        except Exception as exc:
            self._set_error(f"Falha ao baixar asset: {exc}")
        return self.snapshot()

    def remove_plugin(self, plugin_id: str) -> dict[str, Any]:
        try:
            removed_name = self.registry.remove_plugin(plugin_id)
            self._reload_plugins()
            games = self.store.load_games(list(self._plugin_by_name))
            games = {name: status for name, status in games.items() if name in self._plugin_by_name}
            self.store.save_games(games)
            with self._lock:
                if self._selected_game not in self._plugin_by_name:
                    self._selected_game = self.plugins[0]["name"]
                    self._save_selected_game_safe(self._selected_game)
                self._last_error = ""
                self._status_text = f"Plugin removido: {removed_name}"
            self._push_message("success", "Plugin removido", removed_name)
        except Exception as exc:
            self._set_error(f"Falha ao remover plugin: {exc}")
        return self.snapshot()

    def install_using_selected_folder(self) -> dict[str, Any]:
        selected = self.snapshot()["selected_game"]
        plugin = self.plugin_meta(selected)
        folder = self.snapshot()["install_modal"]["selected_folder"]
        if not folder and plugin["requires_install"]:
            self._set_error("Selecione uma pasta antes de instalar.")
            return self.snapshot()
        try:
            message = self.installer.install(plugin, folder)
            self.install_selected_game()
            self._set_status(message)
            self._push_message("success", "Instalação concluída", message)
        except Exception as exc:
            self._set_error(f"Falha na instalação: {exc}")
        return self.snapshot()

    def start_collection(self) -> None:
        with self._lock:
            if self._is_collecting:
                return
            self._collector_session += 1
            collector_session = self._collector_session
            stop_event = threading.Event()
            self._stop_event = stop_event
            self._is_collecting = True
            self._status_text = "Aguardando telemetria..."
            self._last_error = ""
        self._thread = threading.Thread(
            target=self._collector_loop,
            args=(collector_session, stop_event),
            daemon=True,
        )
        self._thread.start()

    def stop_collection(self, wait: bool = False) -> None:
        with self._lock:
            thread = self._thread
            collector_module = self._collector_module
            stop_event = self._stop_event
            self._collector_session += 1
            self._thread = None
            self._collector_module = None
            self._is_collecting = False
            self._status_text = "Parado"
            self._telemetry = {}
        stop_event.set()
        if collector_module is not None and hasattr(collector_module, "shutdown"):
            try:
                collector_module.shutdown()
            except Exception:
                pass
        if wait and thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        self.adjacent_devices.shutdown()
        self.motion_sender.send_defaults(force=True)
        self.panel_sender.send_defaults(force=True)

    def shutdown(self) -> None:
        self.stop_collection(wait=True)
        self.panel_sender.shutdown()
        self.motion_sender.shutdown()
        self.adjacent_devices.shutdown()
        self.telemetry_share.shutdown()
        try:
            self.web_runtime.stop_http()
        except Exception:
            pass
        try:
            self.web_runtime.stop_udp()
        except Exception:
            pass

    def is_game_active(self, game_name: str, active_process_names: set[str] | None = None) -> bool:
        plugin = self.plugin_meta(game_name)
        if self._telemetry_reports_activity(plugin):
            return True
        expected_names = self._expected_process_names(plugin)
        if not expected_names:
            return False
        process_names = active_process_names if active_process_names is not None else self._active_process_names()
        return any(process_name in expected_names for process_name in process_names)

    def _find_first_active_game(self) -> str | None:
        active_process_names = self._active_process_names()
        for game_name in self._plugin_by_name:
            if self.is_game_active(game_name, active_process_names):
                return game_name
        return None

    def _active_process_names(self) -> set[str]:
        names: set[str] = set()
        for process in psutil.process_iter(["name"]):
            try:
                process_name = (process.info["name"] or "").lower()
                if process_name:
                    names.add(process_name)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return names

    def _collector_loop(self, collector_session: int, stop_event: threading.Event) -> None:
        selected = self.snapshot()["selected_game"]
        plugin = self.plugin_meta(selected)
        collector_module = self.registry.load_module(plugin, "telemetry_script")
        if collector_module is None or not hasattr(collector_module, "collect"):
            self._set_error("Jogo não suportado.")
            self.stop_collection()
            return
        with self._lock:
            if collector_session != self._collector_session:
                return
            self._collector_module = collector_module
        try:
            while not stop_event.is_set():
                try:
                    telemetry = collector_module.collect(self._collector_settings(plugin))
                    if stop_event.is_set() or collector_session != self._collector_session:
                        break
                    if self._telemetry_payload_is_active(plugin, telemetry):
                        telemetry = self._apply_merge_rules(plugin, telemetry)
                        telemetry = self._apply_equalization(plugin, telemetry)
                        with self._lock:
                            self._telemetry = telemetry
                            self._last_active_telemetry = dict(telemetry)
                            self._last_active_telemetry_at = time.monotonic()
                            self._status_text = "Coletando telemetria"
                            self._last_error = ""
                        self.motion_sender.send(telemetry)
                        self.panel_sender.send(telemetry)
                        self.adjacent_devices.send(telemetry, True)
                        self._publish_shared_telemetry(telemetry)
                    else:
                        listener_error = str(telemetry.get("_listener_error", "") or "")
                        listener_event = str(telemetry.get("_listener_event", "") or "")
                        with self._lock:
                            recently_active = (
                                time.monotonic() - self._last_active_telemetry_at
                            ) < FARM_RECONNECT_GRACE_SECONDS
                            if recently_active and self._last_active_telemetry:
                                self._telemetry = dict(self._last_active_telemetry)
                                self._status_text = "Reconectando telemetria do farm..."
                            else:
                                self._telemetry = {}
                                self._status_text = self._waiting_status_text(listener_event, listener_error)
                            self._last_error = ""
                        if recently_active and self._last_active_telemetry:
                            self.motion_sender.send(self._last_active_telemetry)
                            self.panel_sender.send(self._last_active_telemetry)
                            self.adjacent_devices.send(self._last_active_telemetry, True)
                            self._publish_shared_telemetry(self._last_active_telemetry)
                        else:
                            self.motion_sender.send_defaults()
                            self.panel_sender.send_defaults()
                            self.adjacent_devices.send({}, False)
                            self._publish_shared_telemetry({})
                    time.sleep(0.02)
                except Exception as exc:
                    self._set_error(f"Erro ao coletar telemetria: {exc}")
                    if stop_event.is_set() or collector_session != self._collector_session:
                        break
                    if not self.is_game_active(selected):
                        self.stop_collection()
                        break
                    time.sleep(0.08)
        finally:
            self._publish_shared_telemetry({})
            with self._lock:
                if collector_session == self._collector_session:
                    self._collector_module = None
                    self._thread = None
                    self._is_collecting = False
                    self._telemetry = {}
                    self._status_text = "Parado"

    def _status_for_game(self, game_name: str) -> str:
        plugin = self.plugin_meta(game_name)
        if not plugin["requires_install"]:
            return "Pronto para coletar"
        installed = self.store.load_games(list(self._plugin_by_name)).get(game_name, "no")
        return "Pronto para coletar" if installed == "yes" else "Necessita instalação"

    def _collector_settings(self, plugin: dict[str, Any] | None = None) -> dict[str, Any]:
        telemetry_config = (plugin or {}).get("telemetry")
        if not isinstance(telemetry_config, dict):
            telemetry_config = {}
        settings = dict(telemetry_config)
        settings.update({
            "speed_unit": self.speed_unit,
            "pressure_unit": self.pressure_unit,
            "temperature_unit": self.temperature_unit,
            "telemetry_ip": telemetry_config.get("bind_ip", "0.0.0.0"),
            "telemetry_port": telemetry_config.get("port", 9999),
            "udp_ip": telemetry_config.get("bind_ip", "0.0.0.0"),
            "udp_port": telemetry_config.get("port", 9999),
        })
        return settings

    def _expected_process_names(self, plugin: dict[str, Any]) -> set[str]:
        names = []
        primary_name = plugin.get("process_name")
        if primary_name:
            names.append(primary_name)
        names.extend(plugin.get("process_names") or [])
        expected_names: set[str] = set()
        for name in names:
            normalized = str(name or "").strip().lower()
            if not normalized:
                continue
            expected_names.add(normalized)
            if normalized.endswith(".exe"):
                expected_names.add(normalized[:-4])
            else:
                expected_names.add(f"{normalized}.exe")
        return expected_names

    def _telemetry_reports_activity(self, plugin: dict[str, Any]) -> bool:
        collector_module = self.registry.load_module(plugin, "telemetry_script")
        if collector_module is None or not hasattr(collector_module, "is_active"):
            return False
        try:
            return bool(collector_module.is_active(self._collector_settings(plugin)))
        except Exception:
            return False

    def _telemetry_payload_is_active(self, plugin: dict[str, Any], telemetry: dict[str, Any]) -> bool:
        if plugin.get("activity_source") == "telemetry":
            return bool(telemetry.get("connected"))
        return bool(telemetry)

    def _waiting_status_text(self, listener_event: str, listener_error: str) -> str:
        if listener_error:
            return f"Pipe do farm com erro: {listener_error}"
        labels = {
            "idle": "Aguardando telemetria...",
            "creating_pipe": "Criando pipe do farm...",
            "waiting_client": "Aguardando o mod do farm conectar...",
            "connected": "Pipe conectado. Aguardando dados do farm...",
            "disconnected": "Mod do farm desconectou do pipe.",
            "listener_error": "Falha ao abrir pipe do farm.",
            "stopped": "Pipe do farm parado.",
        }
        return labels.get(listener_event, "Aguardando telemetria...")

    def _set_status(self, text: str) -> None:
        with self._lock:
            self._status_text = text

    def _set_error(self, text: str) -> None:
        with self._lock:
            self._set_error_locked(text)

    def _set_error_locked(self, text: str) -> None:
        duplicated = self._last_error == text
        self._status_text = "Erro no jogo"
        self._last_error = text
        if not duplicated:
            self._message_seq += 1
            self._ui_messages.append(
                {
                    "id": self._message_seq,
                    "kind": "error",
                    "title": "Erro",
                    "text": text,
                }
            )

    def _push_message(self, kind: str, title: str, text: str) -> None:
        with self._lock:
            self._message_seq += 1
            self._ui_messages.append(
                {
                    "id": self._message_seq,
                    "kind": kind,
                    "title": title,
                    "text": text,
                }
            )

    def _apply_windows_startup(self, enabled: bool) -> None:
        startup_dir = Path(os.getenv("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        startup_dir.mkdir(parents=True, exist_ok=True)
        launcher = startup_dir / "DSW Painel Pro.vbs"
        legacy_launchers = [
            startup_dir / "DSW Painel Pro.cmd",
            startup_dir / "DSW Painel Open Source.cmd",
            startup_dir / "DSW Painel Open Source.vbs",
        ]
        base_dir = get_app_base_dir()
        if enabled:
            args = " --tray" if self._settings.get("minimize_to_tray", True) else ""
            if getattr(sys, "frozen", False):
                command_parts = [str(Path(sys.executable).resolve())]
            else:
                command_parts = [str(Path(sys.executable).resolve()), str((base_dir / "main.py").resolve())]
            if args:
                command_parts.append(args.strip())
            command = " ".join(_quote_vbs_command_part(part) for part in command_parts)
            script = (
                'Set WshShell = CreateObject("WScript.Shell")\n'
                f'WshShell.CurrentDirectory = "{_escape_vbs_string(str(base_dir))}"\n'
                f'WshShell.Run "{_escape_vbs_string(command)}", 0, False\n'
            )
            launcher.write_text(script, encoding="utf-8")
            for legacy_launcher in legacy_launchers:
                if legacy_launcher.exists() and legacy_launcher != launcher:
                    legacy_launcher.unlink()
        elif launcher.exists():
            launcher.unlink()
        if not enabled:
            for legacy_launcher in legacy_launchers:
                if legacy_launcher.exists():
                    legacy_launcher.unlink()

    def _reload_plugins(self) -> None:
        self.plugins = self.registry.refresh()
        self._plugin_by_name = {plugin["name"]: plugin for plugin in self.plugins}
        self._selected_game = self._resolve_selected_game_name(self._selected_game)

    def _save_selected_game_safe(self, game_name: str) -> None:
        try:
            self.store.save_selected_game(game_name)
        except OSError:
            pass

    def _resolve_selected_game_name(self, game_name: str) -> str:
        if game_name in self._plugin_by_name:
            return game_name

        aliases = {
            "Farming Simulator": self._preferred_farming_plugin_name(),
        }
        resolved = aliases.get(game_name)
        if resolved in self._plugin_by_name:
            return resolved
        return self.plugins[0]["name"]

    def _preferred_farming_plugin_name(self) -> str:
        preferred_names = [
            "Farming Simulator 25",
            "Farming Simulator 22",
            "Farming Simulator 19",
        ]
        for name in preferred_names:
            if name in self._plugin_by_name:
                return name
        return self.plugins[0]["name"]

    def _visible_fields_for_plugin(self, plugin: dict[str, Any], telemetry: dict[str, Any]) -> list[str]:
        fields: list[str] = []
        for key in plugin.get("emitted_fields") or []:
            if key not in fields:
                fields.append(key)
        for key in plugin.get("available_extra_fields") or []:
            if key not in fields:
                fields.append(key)
        if fields:
            return fields
        return list(telemetry)

    def _apply_equalization(self, plugin: dict[str, Any], telemetry: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            rules = list(self._settings.get("value_equalization_rules", []))
        if not rules:
            return telemetry

        result = dict(telemetry)
        plugin_id = plugin.get("id", "")
        for rule in rules:
            if not self._rule_matches_game(rule, plugin_id):
                continue

            field_key = rule.get("field_key")
            if field_key not in result:
                continue

            source_value = self._coerce_numeric(result.get(field_key))
            if source_value is None:
                continue

            transformed = self._transform_numeric_value(
                source_value,
                float(rule["source_min"]),
                float(rule["source_max"]),
                float(rule["target_min"]),
                float(rule["target_max"]),
            )
            if transformed is None:
                continue

            original_value = result.get(field_key)
            if isinstance(original_value, bool):
                result[field_key] = transformed >= 0.5
            elif isinstance(original_value, int) and not isinstance(original_value, bool):
                result[field_key] = int(round(transformed))
            else:
                result[field_key] = round(transformed, 3)

        return result

    def _apply_merge_rules(self, plugin: dict[str, Any], telemetry: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            rules = list(self._settings.get("telemetry_merge_rules", []))
        if not rules:
            return telemetry

        result = dict(telemetry)
        plugin_id = plugin.get("id", "")
        for rule in rules:
            if not self._rule_matches_game(rule, plugin_id):
                continue

            source_field_key = rule.get("source_field_key")
            target_field_key = rule.get("target_field_key")
            if source_field_key not in result or not target_field_key:
                continue

            source_value = result.get(source_field_key)
            if rule.get("mode") == "merge":
                target_value = result.get(target_field_key)
                result[target_field_key] = self._merge_telemetry_values(target_value, source_value)
            else:
                result[target_field_key] = source_value

        return result

    def _rule_matches_game(self, rule: dict[str, Any], plugin_id: str) -> bool:
        if rule.get("apply_to_all"):
            return True
        return plugin_id in rule.get("game_ids", [])

    def _coerce_numeric(self, value: Any) -> float | None:
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _merge_telemetry_values(self, target_value: Any, source_value: Any) -> Any:
        if target_value is None:
            return source_value
        if source_value is None:
            return target_value

        if isinstance(target_value, bool) or isinstance(source_value, bool):
            return bool(target_value) or bool(source_value)

        target_numeric = self._coerce_numeric(target_value)
        source_numeric = self._coerce_numeric(source_value)
        if target_numeric is not None and source_numeric is not None:
            return source_value if abs(source_numeric) >= abs(target_numeric) else target_value

        if isinstance(target_value, str) or isinstance(source_value, str):
            parts: list[str] = []
            for value in (target_value, source_value):
                text = str(value).strip()
                if text and text not in parts:
                    parts.append(text)
            return " | ".join(parts) if parts else ""

        return source_value

    def _transform_numeric_value(
        self,
        value: float,
        source_min: float,
        source_max: float,
        target_min: float,
        target_max: float,
    ) -> float | None:
        source_span = source_max - source_min
        if abs(source_span) < 1e-9:
            return None
        normalized = (value - source_min) / source_span
        transformed = target_min + normalized * (target_max - target_min)
        lower = min(target_min, target_max)
        upper = max(target_min, target_max)
        return max(lower, min(upper, transformed))

    def _load_about_template(self) -> str:
        about_path = self.base_dir / "frontend" / "about_dsw.html"
        if not about_path.exists():
            return ""
        try:
            return about_path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _latest_telemetry_for_preview(self) -> dict[str, Any]:
        with self._lock:
            if self._telemetry:
                return dict(self._telemetry)
            if self._last_active_telemetry:
                return dict(self._last_active_telemetry)
        return {}

    def _publish_shared_telemetry(self, telemetry: dict[str, Any]) -> None:
        with self._lock:
            selected_game = self._selected_game
            is_collecting = self._is_collecting
            status_text = self._status_text
        payload = {
            "selected_game": selected_game,
            "is_collecting": is_collecting,
            "status_text": status_text,
            "telemetry": dict(telemetry),
            "updated_at": time.time(),
        }
        self.telemetry_share.publish(payload)
