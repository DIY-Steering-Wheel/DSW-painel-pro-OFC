from __future__ import annotations

import os
import shutil
from pathlib import Path


GAME_DIR_NAME = "FarmingSimulator2019"
MOD_FOLDER_NAME = "farming19"


def search_default_folder():
    for candidate in _candidate_mod_folders():
        if candidate.exists():
            return str(candidate)
    return None


def install(folder, plugin_dir: Path):
    mods_dir = Path(folder)
    mods_dir.mkdir(parents=True, exist_ok=True)
    source = plugin_dir / "payload" / MOD_FOLDER_NAME
    if not source.exists():
        raise RuntimeError(f"Mod nao encontrado no plugin: {source}")
    target = mods_dir / MOD_FOLDER_NAME
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return "Mod Farming Simulator 19 instalado com sucesso."


def uninstall(folder, plugin_dir: Path):
    target = Path(folder) / MOD_FOLDER_NAME
    if target.exists():
        shutil.rmtree(target)
    return "Mod Farming Simulator 19 removido com sucesso."


def _candidate_mod_folders() -> list[Path]:
    home = Path.home()
    candidates = [
        home / "Documents" / "My Games" / GAME_DIR_NAME / "mods",
        home / "OneDrive" / "Documents" / "My Games" / GAME_DIR_NAME / "mods",
        Path(os.getenv("USERPROFILE", "")) / "Documents" / "My Games" / GAME_DIR_NAME / "mods",
    ]
    deduped: list[Path] = []
    seen = set()
    for item in candidates:
        key = str(item).lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped
