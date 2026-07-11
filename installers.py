from __future__ import annotations

from pathlib import Path

try:
    from .plugin_registry import PluginRegistry
except ImportError:  # pragma: no cover
    from plugin_registry import PluginRegistry


class InstallerService:
    def __init__(self, base_dir: Path, registry: PluginRegistry) -> None:
        self.base_dir = base_dir
        self.registry = registry

    def browse_folder(self, window) -> str | None:
        import webview

        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return None
        return result[0]

    def search_default_folder(self, plugin: dict) -> str | None:
        module = self.registry.load_module(plugin, "installer_script")
        if module is None or not hasattr(module, "search_default_folder"):
            return None
        return module.search_default_folder()

    def install(self, plugin: dict, folder: str) -> str:
        module = self.registry.load_module(plugin, "installer_script")
        if module is None or not hasattr(module, "install"):
            return plugin.get("installer", {}).get("success_message", "Este jogo não precisa de instalação.")
        return module.install(folder, Path(plugin["plugin_dir"]))
