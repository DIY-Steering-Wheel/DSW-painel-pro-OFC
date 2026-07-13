from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
import shutil
import time


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "build_nuitka"
DIST_DIR_NAME = "DSW Painel Pro.dist"


def main() -> int:
    version_file_arg = _resolve_version_file_arg()
    optional_modules = [
        "pywintypes",
        "pythoncom",
        "win32file",
        "win32pipe",
    ]
    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--windows-console-mode=disable",
        "--assume-yes-for-downloads",
        "--remove-output",
        "--disable-cache=bytecode",
        "--output-dir=" + str(OUTPUT_DIR),
        "--output-filename=DSW Painel Pro.exe",
        "--company-name=Valdemir",
        "--product-name=DSW Painel Pro",
        "--file-description=DSW Painel Pro",
        "--product-version=1.0.0",
        "--file-version=1.0.0",
        "--windows-icon-from-ico=" + str(BASE_DIR / "app_icon.ico"),
        "--include-data-dir=" + str(BASE_DIR / "bootstrap-5.3.0-dist") + "=bootstrap-5.3.0-dist",
        "--include-data-dir=" + str(BASE_DIR / "bootstrap-icons-1.13.1") + "=bootstrap-icons-1.13.1",
        "--include-data-dir=" + str(BASE_DIR / "frontend") + "=frontend",
        "--include-data-dir=" + str(BASE_DIR / "web") + "=web",
        "--include-data-dir=" + str(BASE_DIR / "Game Plugins") + "=Game Plugins",
        "--include-data-files=" + str(BASE_DIR / "app_icon.ico") + "=app_icon.ico",
        "--include-data-files=" + str(BASE_DIR / "small_icon.ico") + "=small_icon.ico",
        "--include-data-files=" + str(BASE_DIR / "API.md") + "=API.md",
        "--include-data-files=" + str(BASE_DIR / "README.md") + "=README.md",
        "--include-module=serial",
        "--include-module=serial.tools.list_ports_windows",
        "--include-package=lupa",
        "--include-package=psutil",
        "--include-package=qrcode",
        "--include-package=PIL",
        "--include-module=clr_loader",
        "--include-module=pythonnet",
        "--nofollow-import-to=tkinter,test,pytest,PyQt6",
        "--enable-plugin=pyqt5",
        "main.py",
    ]
    for module_name in optional_modules:
        if _module_exists(module_name):
            command.insert(-4, f"--include-module={module_name}")
        else:
            print(f"Skipping optional module not available in environment: {module_name}")
    if version_file_arg:
        command.insert(-2, version_file_arg)

    print("Running:", " ".join(command))
    completed = subprocess.run(command, cwd=BASE_DIR)
    if completed.returncode != 0:
        return completed.returncode

    source_dist_dir = OUTPUT_DIR / "main.dist"
    dist_dir = OUTPUT_DIR / DIST_DIR_NAME
    if source_dist_dir.exists() and source_dist_dir != dist_dir:
        final_dir = _finalize_dist_directory(source_dist_dir, dist_dir)
    else:
        final_dir = dist_dir if dist_dir.exists() else source_dist_dir

    if final_dir.exists():
        print(f"Nuitka build created at: {final_dir}")
    return 0


def _resolve_version_file_arg() -> str | None:
    for candidate_name in ("Versão.json", "Versao.json", "VersÃ£o.json", "VersÃƒÂ£o.json"):
        candidate_path = BASE_DIR / candidate_name
        if candidate_path.exists():
            return "--include-data-files=" + str(candidate_path) + "=" + candidate_name
    return None


def _finalize_dist_directory(source_dist_dir: Path, dist_dir: Path) -> Path:
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    for _ in range(5):
        try:
            source_dist_dir.rename(dist_dir)
            return dist_dir
        except PermissionError:
            time.sleep(1.0)
    print(
        "Aviso: o build foi gerado com sucesso, mas o Windows bloqueou a renomeacao final da pasta de saida. "
        f"Usando '{source_dist_dir.name}' como pasta final."
    )
    return source_dist_dir


def _module_exists(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


if __name__ == "__main__":
    raise SystemExit(main())
