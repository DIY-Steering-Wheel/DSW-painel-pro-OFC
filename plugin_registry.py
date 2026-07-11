from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class PluginRegistry:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.plugins_dir = base_dir / "Game Plugins"
        self.index_path = self.plugins_dir / "index.json"
        self.downloads_dir = Path.home() / "Downloads" / "DSW Painel Pro"
        self._plugins_cache: list[dict[str, Any]] | None = None
        self._module_cache: dict[tuple[str, str], Any] = {}

    def load_plugins(self) -> list[dict[str, Any]]:
        if self._plugins_cache is not None:
            return self._plugins_cache

        index = self.load_index()
        plugins = []
        for entry in index.get("plugins", []):
            plugin_dir = self.plugins_dir / entry["folder"]
            manifest_path = plugin_dir / "plugin.json"
            with manifest_path.open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            manifest["folder"] = entry["folder"]
            manifest["icon"] = f"Game Plugins/{entry['folder']}/{manifest['icon']}"
            manifest["manifest_path"] = str(manifest_path)
            manifest["plugin_dir"] = str(plugin_dir)
            manifest["built_in"] = bool(entry.get("built_in", False))
            plugins.append(manifest)
        self._plugins_cache = plugins
        return plugins

    def load_index(self) -> dict[str, Any]:
        with self.index_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save_index(self, data: dict[str, Any]) -> None:
        with self.index_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

    def refresh(self) -> list[dict[str, Any]]:
        self._plugins_cache = None
        self._module_cache = {}
        return self.load_plugins()

    def by_name(self, game_name: str) -> dict[str, Any]:
        return next(plugin for plugin in self.load_plugins() if plugin["name"] == game_name)

    def load_module(self, plugin: dict[str, Any], module_key: str):
        relative_path = plugin.get(module_key)
        if not relative_path:
            return None
        cache_key = (plugin["id"], module_key)
        if cache_key in self._module_cache:
            return self._module_cache[cache_key]

        module_path = Path(plugin["plugin_dir"]) / relative_path
        module_name = f"versao_nova_plugin_{plugin['id'].replace('-', '_')}_{module_key.replace('.', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Nao foi possivel carregar o modulo {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        self._module_cache[cache_key] = module
        return module

    def import_package(self, source_path: str) -> list[str]:
        if not source_path:
            raise RuntimeError("Selecione um pacote de plugin antes de importar.")

        source = Path(source_path)
        if not source.exists():
            raise RuntimeError("O pacote informado nao existe mais.")

        with tempfile.TemporaryDirectory(prefix="dsw_plugin_import_") as temp_dir:
            staging_root = Path(temp_dir)
            extracted_root = self._prepare_import_source(source, staging_root)
            plugin_dirs = self._discover_plugin_dirs(extracted_root)
            if not plugin_dirs:
                raise RuntimeError("Nenhum plugin valido foi encontrado no pacote.")

            index = self.load_index()
            existing_folders = {entry["folder"] for entry in index.get("plugins", [])}
            existing_ids = {plugin["id"] for plugin in self.load_plugins()}
            imported_names: list[str] = []

            for plugin_dir in plugin_dirs:
                manifest_path = plugin_dir / "plugin.json"
                with manifest_path.open("r", encoding="utf-8") as handle:
                    manifest = json.load(handle)
                folder_name = plugin_dir.name
                plugin_id = manifest["id"]
                if folder_name in existing_folders:
                    raise RuntimeError(f"Ja existe um plugin na pasta '{folder_name}'.")
                if plugin_id in existing_ids:
                    raise RuntimeError(f"Ja existe um plugin com id '{plugin_id}'.")
                shutil.copytree(plugin_dir, self.plugins_dir / folder_name)
                index.setdefault("plugins", []).append({"folder": folder_name, "built_in": False})
                existing_folders.add(folder_name)
                existing_ids.add(plugin_id)
                imported_names.append(manifest["name"])

            self.save_index(index)
            self.refresh()
            return imported_names

    def remove_plugin(self, plugin_id: str) -> str:
        plugin = next((item for item in self.load_plugins() if item["id"] == plugin_id), None)
        if plugin is None:
            raise RuntimeError("Plugin nao encontrado.")
        if plugin.get("built_in"):
            raise RuntimeError("Plugins padrao nao podem ser excluidos.")

        plugin_dir = Path(plugin["plugin_dir"])
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)

        index = self.load_index()
        index["plugins"] = [entry for entry in index.get("plugins", []) if entry.get("folder") != plugin["folder"]]
        self.save_index(index)
        self.refresh()
        return plugin["name"]

    def fetch_github_releases(self, repo_url: str) -> dict[str, Any]:
        owner, repo = self._parse_github_repo(repo_url)
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        payload = self._get_json(api_url)
        releases: list[dict[str, Any]] = []
        for item in payload:
            assets = []
            for asset in item.get("assets", []):
                name = asset.get("name") or "arquivo"
                assets.append(
                    {
                        "id": asset.get("id"),
                        "name": name,
                        "size": int(asset.get("size") or 0),
                        "content_type": asset.get("content_type") or "",
                        "download_count": int(asset.get("download_count") or 0),
                        "download_url": asset.get("browser_download_url") or "",
                        "updated_at": asset.get("updated_at") or "",
                        "is_zip": name.lower().endswith(".zip"),
                    }
                )
            releases.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name") or item.get("tag_name") or "Release sem nome",
                    "tag_name": item.get("tag_name") or "",
                    "published_at": item.get("published_at") or "",
                    "html_url": item.get("html_url") or f"https://github.com/{owner}/{repo}",
                    "body": item.get("body") or "",
                    "prerelease": bool(item.get("prerelease", False)),
                    "draft": bool(item.get("draft", False)),
                    "assets": assets,
                }
            )
        return {
            "repo_url": f"https://github.com/{owner}/{repo}",
            "repo_name": f"{owner}/{repo}",
            "releases": releases,
        }

    def download_release_asset(self, download_url: str, asset_name: str, action: str = "download") -> dict[str, Any]:
        if not download_url:
            raise RuntimeError("Arquivo do release sem link de download.")

        filename = self._sanitize_filename(asset_name or "plugin.zip")
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        target_path = self.downloads_dir / filename
        self._download_file(download_url, target_path)

        result: dict[str, Any] = {
            "path": str(target_path),
            "filename": target_path.name,
            "action": action,
        }
        if action == "extract":
            if target_path.suffix.lower() != ".zip":
                raise RuntimeError("Somente arquivos ZIP podem ser extraidos automaticamente.")
            extract_dir = self.downloads_dir / target_path.stem
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            shutil.unpack_archive(str(target_path), str(extract_dir))
            result["extract_dir"] = str(extract_dir)
        elif action == "import":
            if target_path.suffix.lower() != ".zip":
                raise RuntimeError("Somente arquivos ZIP podem ser importados automaticamente.")
            result["imported_names"] = self.import_package(str(target_path))
        return result

    def _prepare_import_source(self, source: Path, staging_root: Path) -> Path:
        if source.is_dir():
            target = staging_root / source.name
            shutil.copytree(source, target)
            return staging_root
        if source.suffix.lower() == ".zip":
            shutil.unpack_archive(str(source), str(staging_root))
            return staging_root
        if source.suffix.lower() == ".iso":
            self._extract_iso(source, staging_root)
            return staging_root
        raise RuntimeError("Formato nao suportado. Use pasta, ZIP ou ISO.")

    def _parse_github_repo(self, repo_url: str) -> tuple[str, str]:
        parsed = urlparse((repo_url or "").strip())
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com":
            raise RuntimeError("Informe um link valido de repositorio do GitHub.")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            raise RuntimeError("Link do GitHub incompleto. Use um repositorio como https://github.com/owner/repo.")
        owner, repo = parts[0], re.sub(r"\.git$", "", parts[1], flags=re.IGNORECASE)
        return owner, repo

    def _get_json(self, url: str) -> Any:
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "DSW-Painel-Pro",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                raise RuntimeError("Repositorio nao encontrado ou sem releases publicos.") from exc
            if exc.code == 403:
                raise RuntimeError("GitHub recusou a consulta agora. Tente novamente em instantes.") from exc
            raise RuntimeError(f"Falha ao consultar GitHub: HTTP {exc.code}.") from exc
        except URLError as exc:
            raise RuntimeError(f"Falha de rede ao consultar GitHub: {exc.reason}") from exc

    def _download_file(self, url: str, target_path: Path) -> None:
        request = Request(url, headers={"User-Agent": "DSW-Painel-Pro"})
        try:
            with urlopen(request, timeout=60) as response, target_path.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        except HTTPError as exc:
            raise RuntimeError(f"Falha ao baixar arquivo: HTTP {exc.code}.") from exc
        except URLError as exc:
            raise RuntimeError(f"Falha de rede ao baixar arquivo: {exc.reason}") from exc

    def _sanitize_filename(self, name: str) -> str:
        clean = re.sub(r'[<>:"/\\\\|?*]+', "-", name).strip().strip(".")
        return clean or "plugin.zip"

    def _discover_plugin_dirs(self, root: Path) -> list[Path]:
        candidates: list[Path] = []
        if (root / "plugin.json").exists():
            candidates.append(root)
        for manifest_path in root.rglob("plugin.json"):
            parent = manifest_path.parent
            if parent not in candidates:
                candidates.append(parent)
        return sorted(candidates, key=lambda item: len(item.parts))

    def _extract_iso(self, source: Path, staging_root: Path) -> None:
        image_path = str(source).replace("'", "''")
        target_path = str(staging_root).replace("'", "''")
        script = (
            f"$img='{image_path}';"
            f"$dst='{target_path}';"
            "$mount=$null;"
            "try {"
            " $mount=Mount-DiskImage -ImagePath $img -PassThru;"
            " Start-Sleep -Milliseconds 400;"
            " $drive=($mount | Get-Volume).DriveLetter;"
            " if (-not $drive) { throw 'Nao foi possivel montar o ISO.' }"
            " Copy-Item -Path ($drive + ':\\*') -Destination $dst -Recurse -Force;"
            "} finally {"
            " if ($mount) { Dismount-DiskImage -ImagePath $img | Out-Null }"
            "}"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True, capture_output=True, text=True)
