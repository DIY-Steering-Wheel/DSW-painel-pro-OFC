from __future__ import annotations

import shutil
from pathlib import Path


MOD_FILES = (
    ("VehicleTelemetry.dll", Path("VehicleTelemetry.dll")),
    ("websocket-sharp.dll", Path("References") / "WebSocketSharp.dll"),
)


def search_default_folder():
    return None


def install(folder, plugin_dir: Path):
    mods_dir = Path(folder)
    mods_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for source_name, relative_target in MOD_FILES:
        source = plugin_dir / "payload" / source_name
        if not source.exists():
            raise RuntimeError(f"Arquivo do mod nao encontrado: {source}")
        target = mods_dir / relative_target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(str(relative_target))
    return "Arquivos do mod copiados: " + ", ".join(copied) + "."


def uninstall(folder, plugin_dir: Path):
    mods_dir = Path(folder)
    removed = []
    for _source_name, relative_target in MOD_FILES:
        target = mods_dir / relative_target
        if target.exists():
            target.unlink()
            removed.append(str(relative_target))
    if removed:
        return "Arquivos removidos: " + ", ".join(removed) + "."
    return "Nenhuma DLL do My Summer Car foi encontrada para remover."
