from __future__ import annotations

import ctypes
import time
from pathlib import Path

import webview

try:
    from .app_api import NewAppApi
except ImportError:  # pragma: no cover
    from app_api import NewAppApi



def run() -> None:
    api = NewAppApi()
    base_dir = Path(__file__).resolve().parent
    webview.create_window(
        "DSW Painel Open - Nova Versao",
        url=(base_dir / "frontend" / "index.html").as_uri(),
        js_api=api,
        width=800,
        height=484,
        min_size=(1200, 540),
        resizable=False,
    )
    webview.start(_apply_windows_dark_titlebar, debug=False)


def _apply_windows_dark_titlebar() -> None:
    time.sleep(0.25)
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return
        value = ctypes.c_int(1)
        for attribute in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                ctypes.c_uint(attribute),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
    except Exception:
        return


if __name__ == "__main__":
    run()
