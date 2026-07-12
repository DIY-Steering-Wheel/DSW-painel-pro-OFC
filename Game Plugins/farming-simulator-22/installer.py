from __future__ import annotations

import os
import shutil
from pathlib import Path


GAME_DIR_NAME = "FarmingSimulator2022"
SOURCE_MOD_FOLDER_NAME = "farming22"
TARGET_MOD_FOLDER_NAME = "TelemetriaFarmingSimulator22"
LEGACY_MOD_FOLDER_NAMES = ("farming22",)


def search_default_folder():
    for candidate in _candidate_mod_folders():
        if candidate.exists():
            return str(candidate)
    return None


def install(folder, plugin_dir: Path):
    mods_dir = Path(folder)
    mods_dir.mkdir(parents=True, exist_ok=True)
    source = plugin_dir / "payload" / SOURCE_MOD_FOLDER_NAME
    if not source.exists():
        raise RuntimeError(f"Mod nao encontrado no plugin: {source}")
    _remove_existing_targets(mods_dir)
    target = mods_dir / TARGET_MOD_FOLDER_NAME
    shutil.copytree(source, target)
    return "Mod Farming Simulator 22 instalado com sucesso."


def uninstall(folder, plugin_dir: Path):
    _remove_existing_targets(Path(folder))
    return "Mod Farming Simulator 22 removido com sucesso."


def _remove_existing_targets(mods_dir: Path) -> None:
    for folder_name in (TARGET_MOD_FOLDER_NAME, *LEGACY_MOD_FOLDER_NAMES):
        target = mods_dir / folder_name
        if target.exists():
            shutil.rmtree(target)


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
