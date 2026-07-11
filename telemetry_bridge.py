from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from collections import deque
from pathlib import Path
from typing import Any

import psutil

try:
    from .config_store import ConfigStore
    from .constants import PANEL_FIELDS
    from .installers import InstallerService
    from .plugin_registry import PluginRegistry
    from .runtime_paths import get_app_base_dir
    from .serial_services import MotionSender, PanelSender, build_telemetry_rows
    from .web_runtime import WebRuntimeService
except ImportError:  # pragma: no cover
    from config_store import ConfigStore
    from constants import PANEL_FIELDS
    from installers import InstallerService
    from plugin_registry import PluginRegistry
    from runtime_paths import get_app_base_dir
    from serial_services import MotionSender, PanelSender, build_telemetry_rows
    from web_runtime import WebRuntimeService


class TelemetryBridge:
    def __init__(self) -> None:
        self.base_dir = get_app_base_dir()
        self.store = ConfigStore()
        self.registry = PluginRegistry(self.base_dir)
        self.panel_sender = PanelSender(self.store)
        self.motion_sender = MotionSender(self.store)
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
        self._selected_game = self.store.load_selected_game(self.plugins[0]["name"])
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
        emitted_fields = selected_plugin.get("emitted_fields") or list(telemetry)
        installed_games = self.store.load_games(list(self._plugin_by_name))
        panel_status = self.panel_sender.status(collecting)
        motion_status = self.motion_sender.status(collecting)

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
                    "is_active_process": self.is_game_active(game_name),
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
            "panel_fields": [{"key": field.key, "label": field.label, "default": field.default} for field in PANEL_FIELDS],
            "motion_config": self.store.load_motion_config(),
            "motion_preview": self.motion_sender.preview(telemetry),
            "basic_settings": settings,
            "available_ports": self.panel_sender.list_ports(),
            "device_status": {
                "panel": panel_status,
                "motion": motion_status,
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
                self.store.save_selected_game(active_game)
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
                self.store.save_selected_game(game_name)
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
        return self._plugin_by_name[game_name]

    def set_auto_start(self, enabled: bool) -> dict[str, Any]:
        with self._lock:
            self._settings = self.store.save_settings({"auto_start_enabled": bool(enabled)})
        return self.snapshot()

    def save_basic_settings(self, data: dict[str, Any]) -> dict[str, Any]:
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
        self.web_runtime.save_config(data)
        return self.snapshot()

    def import_template_package(self) -> dict[str, Any]:
        try:
            package_path = self.snapshot()["template_manager"]["selected_package"]
            imported_names = self.web_runtime.import_template_archive(package_path)
            with self._lock:
                self._template_package_path = ""
            imported_templates = self.web_runtime.load_template_catalog()
            if imported_names:
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
                    self.store.save_selected_game(self._selected_game)
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
                        self.store.save_selected_game(self._selected_game)
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
                    self.store.save_selected_game(self._selected_game)
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
        selected = self.snapshot()["selected_game"]
        if not self.is_game_active(selected):
            self._set_error("Abra o jogo antes de iniciar a telemetria.")
            return
        with self._lock:
            if self._is_collecting:
                return
            self._is_collecting = True
            self._status_text = "Iniciando coleta..."
            self._last_error = ""
            self._stop_event.clear()
        self._thread = threading.Thread(target=self._collector_loop, daemon=True)
        self._thread.start()

    def stop_collection(self, wait: bool = False) -> None:
        thread = self._thread
        collector_module = self._collector_module
        with self._lock:
            self._is_collecting = False
            self._status_text = "Parado"
        self._stop_event.set()
        if wait and thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        if collector_module is not None and hasattr(collector_module, "shutdown"):
            try:
                collector_module.shutdown()
            except Exception:
                pass
        self._collector_module = None

    def is_game_active(self, game_name: str) -> bool:
        executable_name = self.plugin_meta(game_name).get("process_name")
        if not executable_name:
            return False
        expected_names = {executable_name.lower()}
        if executable_name.lower().endswith(".exe"):
            expected_names.add(executable_name[:-4].lower())
        else:
            expected_names.add(f"{executable_name}.exe".lower())
        for process in psutil.process_iter(["name"]):
            try:
                process_name = (process.info["name"] or "").lower()
                if process_name in expected_names:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

    def _find_first_active_game(self) -> str | None:
        for game_name in self._plugin_by_name:
            if self.is_game_active(game_name):
                return game_name
        return None

    def _collector_loop(self) -> None:
        selected = self.snapshot()["selected_game"]
        plugin = self.plugin_meta(selected)
        collector_module = self.registry.load_module(plugin, "telemetry_script")
        if collector_module is None or not hasattr(collector_module, "collect"):
            self._set_error("Jogo não suportado.")
            self.stop_collection()
            return
        self._collector_module = collector_module
        try:
            while not self._stop_event.is_set():
                try:
                    telemetry = collector_module.collect(
                        {
                            "speed_unit": self.speed_unit,
                            "pressure_unit": self.pressure_unit,
                            "temperature_unit": self.temperature_unit,
                        }
                    )
                    with self._lock:
                        self._telemetry = telemetry
                        self._status_text = "Coletando telemetria"
                        self._last_error = ""
                    self.motion_sender.send(telemetry)
                    self.panel_sender.send(telemetry)
                    time.sleep(0.02)
                except Exception as exc:
                    self._set_error(f"Erro ao coletar telemetria: {exc}")
                    if not self.is_game_active(selected):
                        self.stop_collection()
                        break
                    time.sleep(0.08)
        finally:
            self._set_status("Parado")

    def _status_for_game(self, game_name: str) -> str:
        plugin = self.plugin_meta(game_name)
        if not plugin["requires_install"]:
            return "Pronto para coletar"
        installed = self.store.load_games(list(self._plugin_by_name)).get(game_name, "no")
        return "Pronto para coletar" if installed == "yes" else "Necessita instalação"

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
        launcher = startup_dir / "DSW Painel Pro.cmd"
        old_launcher = startup_dir / "DSW Painel Open Source.cmd"
        if enabled:
            command = f'"{sys.executable}" "{Path.cwd() / "main.py"}"'
            launcher.write_text(f"@echo off\nstart \"\" {command}\n", encoding="utf-8")
            if old_launcher.exists() and old_launcher != launcher:
                old_launcher.unlink()
        elif launcher.exists():
            launcher.unlink()
        if not enabled and old_launcher.exists():
            old_launcher.unlink()

    def _reload_plugins(self) -> None:
        self.plugins = self.registry.refresh()
        self._plugin_by_name = {plugin["name"]: plugin for plugin in self.plugins}

    def _load_about_template(self) -> str:
        about_path = self.base_dir / "frontend" / "about_dsw.html"
        if not about_path.exists():
            return ""
        try:
            return about_path.read_text(encoding="utf-8")
        except OSError:
            return ""
