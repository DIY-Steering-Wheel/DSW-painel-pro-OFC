from __future__ import annotations

from pathlib import Path

from cx_Freeze import Executable, setup


BASE_DIR = Path(__file__).resolve().parent
BUILD_DIR = BASE_DIR / "build" / "DSW Painel Pro"

INCLUDE_FILES = [
    ("bootstrap-5.3.0-dist", "bootstrap-5.3.0-dist"),
    ("bootstrap-icons-1.13.1", "bootstrap-icons-1.13.1"),
    ("frontend", "frontend"),
    ("web", "web"),
    ("Game Plugins", "Game Plugins"),
    ("app_icon.ico", "app_icon.ico"),
    ("small_icon.ico", "small_icon.ico"),
    ("API.md", "API.md"),
    ("README.md", "README.md"),
]

for candidate_name in ("Versão.json", "Versao.json", "VersÃ£o.json"):
    candidate_path = BASE_DIR / candidate_name
    if candidate_path.exists():
        INCLUDE_FILES.append((str(candidate_path), candidate_name))
        break

BUILD_EXE_OPTIONS = {
    "build_exe": str(BUILD_DIR),
    "include_files": INCLUDE_FILES,
    "packages": ["encodings", "webview", "psutil", "qrcode", "serial"],
    "includes": [
        "PIL",
        "runtime_paths",
        "pywintypes",
        "pythoncom",
        "win32file",
        "win32pipe",
        "win32event",
        "win32api",
        "win32con",
        "win32gui",
        "win32process",
        "win32timezone",
    ],
    "include_msvcr": True,
    "optimize": 1,
}


setup(
    name="DSW Painel Pro",
    version="1.0.0",
    description="DSW Painel Pro",
    options={"build_exe": BUILD_EXE_OPTIONS},
    executables=[
        Executable(
            script="main.py",
            base="Win32GUI",
            target_name="DSW Painel Pro.exe",
            icon="app_icon.ico",
        )
    ],
)
