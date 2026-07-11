from __future__ import annotations

import ctypes
import os
import shutil
import string
from pathlib import Path


def search_default_folder():
    for drive in _available_drives():
        for root, _dirs, files in os.walk(drive):
            if "amtrucks.exe" in files:
                bin_path = os.path.basename(root)
                if bin_path in ["win_x86", "win_x64"]:
                    return os.path.dirname(os.path.dirname(root))
    return None


def install(folder, plugin_dir: Path):
    x86_folder = Path(folder) / "bin" / "win_x86" / "plugins"
    x64_folder = Path(folder) / "bin" / "win_x64" / "plugins"
    x86_folder.mkdir(parents=True, exist_ok=True)
    x64_folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(plugin_dir / "payload" / "x86" / "ats-telemetry.dll", x86_folder / "ats-telemetry.dll")
    shutil.copy(plugin_dir / "payload" / "x64" / "ats-telemetry.dll", x64_folder / "ats-telemetry.dll")
    return "Plugin ATS instalado com sucesso."


def uninstall(folder, _plugin_dir: Path):
    targets = [
        Path(folder) / "bin" / "win_x86" / "plugins" / "ats-telemetry.dll",
        Path(folder) / "bin" / "win_x64" / "plugins" / "ats-telemetry.dll",
    ]
    for target in targets:
        if target.exists():
            target.unlink()
    return "Plugin ATS removido com sucesso."


def _available_drives():
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    return [f"{letter}:\\" for letter, mask in zip(string.ascii_uppercase, bin(bitmask)[:0:-1]) if mask == "1"]
