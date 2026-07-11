from __future__ import annotations

import shutil
from pathlib import Path


MOD_FILES = ("websocket-sharp.dll",)


def search_default_folder():
    return None


def install(folder, plugin_dir: Path):
    mods_dir = Path(folder)
    mods_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in MOD_FILES:
        source = plugin_dir / "payload" / name
        if not source.exists():
            raise RuntimeError(f"Arquivo do mod nao encontrado: {source}")
        target = mods_dir / name
        shutil.copy2(source, target)
        copied.append(name)
    return f"DLL copiada para a pasta Mods: {', '.join(copied)}."


def uninstall(folder, plugin_dir: Path):
    mods_dir = Path(folder)
    removed = []
    for name in MOD_FILES:
        target = mods_dir / name
        if target.exists():
            target.unlink()
            removed.append(name)
    if removed:
        return f"DLL removida da pasta Mods: {', '.join(removed)}."
    return "Nenhuma DLL do My Summer Car foi encontrada para remover."
