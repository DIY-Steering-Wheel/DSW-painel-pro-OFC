from __future__ import annotations

import ctypes
import time
from pathlib import Path

import webview

try:
    from .app_api import NewAppApi
    from .runtime_paths import get_app_base_dir
except ImportError:  # pragma: no cover
    from app_api import NewAppApi
    from runtime_paths import get_app_base_dir


APP_TITLE = "DSW Painel Pro - By Valdemir"


def run() -> None:
    api = NewAppApi()
    base_dir = get_app_base_dir()
    window = webview.create_window(
        APP_TITLE,
        url=(base_dir / "frontend" / "index.html").as_uri(),
        js_api=api,
        width=800,
        height=581,
        min_size=(1200, 648),
        resizable=False,
        background_color="#111111",
    )
    webview.start(_apply_windows_dark_titlebar, args=(window,), debug=False)


def _apply_windows_dark_titlebar(window: webview.Window) -> None:
    try:
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi
        window.events.shown.wait(15)
        hwnd = None
        for _ in range(40):
            try:
                from webview.platforms import winforms

                form = winforms.BrowserView.instances.get(window.uid)
                if form is not None:
                    hwnd = int(form.Handle.ToInt32())
            except Exception:
                hwnd = None

            if not hwnd:
                hwnd = user32.FindWindowW(None, APP_TITLE) or user32.GetForegroundWindow()
            if hwnd:
                break
            time.sleep(0.15)
        if not hwnd:
            return

        immersive_dark = ctypes.c_int(1)
        caption_color = ctypes.c_uint(0x1E1E1E)
        text_color = ctypes.c_uint(0xFFFFFF)

        for attribute in (20, 19):
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                ctypes.c_uint(attribute),
                ctypes.byref(immersive_dark),
                ctypes.sizeof(immersive_dark),
            )
        for attribute, value in ((35, caption_color), (36, text_color)):
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                ctypes.c_uint(attribute),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
    except Exception:
        return


if __name__ == "__main__":
    run()
