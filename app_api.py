from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import webview

try:
    from .telemetry_bridge import TelemetryBridge
except ImportError:  # pragma: no cover
    from telemetry_bridge import TelemetryBridge


class NewAppApi:
    def __init__(self) -> None:
        self.bridge = TelemetryBridge()

    def bootstrap(self) -> dict[str, Any]:
        state = self.bridge.refresh_games()
        if state["basic_settings"].get("detect_open_game_on_start"):
            state = self.bridge.auto_select_active_game()
            selected = state["selected_game"]
            active = next((game["is_active_process"] for game in state["games"] if game["name"] == selected), False)
            installed = next((game["installed"] for game in state["games"] if game["name"] == selected), "no")
            if active and installed == "yes" and not state["is_collecting"]:
                self.bridge.start_collection()
                state = self.bridge.snapshot()
        elif state["footer"]["auto_start_enabled"] and not state["is_collecting"]:
            selected = state["selected_game"]
            installed = next((game["installed"] for game in state["games"] if game["name"] == selected), "no")
            if installed == "yes":
                self.bridge.start_collection()
                state = self.bridge.snapshot()
        return state

    def poll_state(self) -> dict[str, Any]:
        return self.bridge.auto_manage_active_game()

    def select_game(self, game_name: str) -> dict[str, Any]:
        return self.bridge.select_game(game_name)

    def toggle_action(self) -> dict[str, Any]:
        return self.bridge.toggle_selected_game()

    def refresh_games(self) -> dict[str, Any]:
        return self.bridge.refresh_games()

    def detect_active_game(self) -> dict[str, Any]:
        return self.bridge.auto_select_active_game()

    def open_panel_config(self) -> dict[str, Any]:
        return self.bridge.snapshot()

    def open_motion_config(self) -> dict[str, Any]:
        return self.bridge.snapshot()

    def save_panel_config(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.bridge.save_panel_config(data)

    def save_motion_config(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.bridge.save_motion_config(data)

    def set_auto_start(self, enabled: bool) -> dict[str, Any]:
        return self.bridge.set_auto_start(enabled)

    def save_basic_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.bridge.save_basic_settings(data)

    def apply_selected_game_unit_defaults(self) -> dict[str, Any]:
        return self.bridge.apply_selected_game_unit_defaults()

    def auto_install_search(self) -> dict[str, Any]:
        plugin = self.bridge.plugin_meta(self.bridge.snapshot()["selected_game"])
        folder = self.bridge.installer.search_default_folder(plugin)
        if folder:
            return self.bridge.set_install_folder(folder)
        return self.bridge.snapshot()

    def browse_install_folder(self) -> dict[str, Any]:
        if not webview.windows:
            return self.bridge.snapshot()
        folder = self.bridge.installer.browse_folder(webview.windows[0])
        if folder:
            return self.bridge.set_install_folder(folder)
        return self.bridge.snapshot()

    def install_selected_game_modal(self) -> dict[str, Any]:
        return self.bridge.install_using_selected_folder()

    def browse_plugin_package(self) -> dict[str, Any]:
        if not webview.windows:
            return self.bridge.snapshot()
        result = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False)
        if result:
            return self.bridge.set_plugin_package_path(result[0])
        return self.bridge.snapshot()

    def import_plugin_package(self) -> dict[str, Any]:
        return self.bridge.import_plugin_package()

    def remove_plugin(self, plugin_id: str) -> dict[str, Any]:
        return self.bridge.remove_plugin(plugin_id)

    def set_plugin_github_url(self, repo_url: str) -> dict[str, Any]:
        return self.bridge.set_plugin_github_url(repo_url)

    def fetch_plugin_github_releases(self) -> dict[str, Any]:
        return self.bridge.fetch_plugin_github_releases()

    def clear_plugin_github_releases(self) -> dict[str, Any]:
        return self.bridge.clear_plugin_github_releases()

    def download_plugin_release_asset(self, download_url: str, asset_name: str, action: str) -> dict[str, Any]:
        return self.bridge.download_plugin_release_asset(download_url, asset_name, action)

    def save_web_server_config(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.bridge.save_web_server_config(data)

    def start_web_server(self) -> dict[str, Any]:
        return self.bridge.start_web_server()

    def stop_web_server(self) -> dict[str, Any]:
        return self.bridge.stop_web_server()

    def start_udp_server(self) -> dict[str, Any]:
        return self.bridge.start_udp_server()

    def stop_udp_server(self) -> dict[str, Any]:
        return self.bridge.stop_udp_server()

    def browse_web_bundle_zip(self) -> dict[str, Any]:
        if not webview.windows:
            return self.bridge.snapshot()
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("ZIP files (*.zip)",),
        )
        if result:
            return self.bridge.set_template_package_path(result[0])
        return self.bridge.snapshot()

    def import_web_bundle_zip(self) -> dict[str, Any]:
        return self.bridge.import_template_package()

    def delete_template(self, template_id: str) -> dict[str, Any]:
        return self.bridge.delete_template(template_id)

    def uninstall_selected_game_modal(self) -> dict[str, Any]:
        return self.bridge.uninstall_selected_game()

    def open_external_url(self, url: str) -> bool:
        parsed = urlparse(url or "")
        if parsed.scheme not in {"http", "https"}:
            return False
        return self.bridge.open_external_url(url)
