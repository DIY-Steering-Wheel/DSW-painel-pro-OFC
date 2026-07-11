from __future__ import annotations

import ctypes
import os
import string
from pathlib import Path


def search_default_folder():
    for drive in _available_drives():
        for root, _dirs, files in os.walk(drive):
            if "cfg.txt" in files:
                return root
    return None


def install(folder, plugin_dir: Path):
    config_path = Path(folder) / "cfg.txt"
    defaults = {
        "OutSim Mode": "1",
        "OutSim Delay": "10",
        "OutSim IP": "127.0.0.1",
        "OutSim Port": "46542",
        "OutSim ID": "0",
        "OutSim Opts": "1ff",
        "OutGauge Mode": "2",
        "OutGauge Delay": "10",
        "OutGauge IP": "127.0.0.1",
        "OutGauge Port": "46541",
        "OutGauge ID": "0",
    }
    if config_path.exists():
        lines = config_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    else:
        lines = []
    for key, value in defaults.items():
        matched = False
        for index, line in enumerate(lines):
            if line.startswith(key):
                lines[index] = f"{key} {value}"
                matched = True
                break
        if not matched:
            lines.append(f"{key} {value}")
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "Configuração do LFS aplicada com sucesso."


def _available_drives():
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    return [f"{letter}:\\" for letter, mask in zip(string.ascii_uppercase, bin(bitmask)[:0:-1]) if mask == "1"]
