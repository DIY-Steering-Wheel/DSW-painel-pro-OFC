from __future__ import annotations

import ctypes
import os
import sys
import time
import traceback
from pathlib import Path

import webview

try:
    from .app_api import NewAppApi
    from .runtime_paths import get_app_base_dir
except ImportError:  # pragma: no cover
    from app_api import NewAppApi
    from runtime_paths import get_app_base_dir


APP_TITLE = "DSW Painel Pro - By Valdemir"
MUTEX_NAME = "Local\\DSWPainelProSingleton"
_SINGLE_INSTANCE_HANDLE = None


def run() -> None:
    if not _ensure_single_instance():
        _show_already_running_message()
        return

    try:
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
            hidden=False,
            background_color="#111111",
        )
        window.events.closing += api.shutdown
        window.events.closed += api.shutdown
        webview.start(_bootstrap_windows_ui, args=(window,), debug=False)
    except Exception as exc:
        log_path = _write_startup_failure(exc)
        _show_startup_failure_message(log_path)
        raise
    finally:
        _release_single_instance()


def _bootstrap_windows_ui(window: webview.Window) -> None:
    _apply_windows_dark_titlebar(window, wait_for_show=True)


def _apply_windows_dark_titlebar(window: webview.Window, wait_for_show: bool = True) -> None:
    try:
        if wait_for_show:
            window.events.shown.wait(15)
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi
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


def _ensure_single_instance() -> bool:
    global _SINGLE_INSTANCE_HANDLE
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return True
    error_code = kernel32.GetLastError()
    if error_code == 183:
        kernel32.CloseHandle(handle)
        return False
    _SINGLE_INSTANCE_HANDLE = handle
    return True


def _release_single_instance() -> None:
    global _SINGLE_INSTANCE_HANDLE
    handle = _SINGLE_INSTANCE_HANDLE
    if handle:
        try:
            ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass
    _SINGLE_INSTANCE_HANDLE = None


def _show_already_running_message() -> None:
    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            "O DSW Painel Pro ja esta rodando. Se a janela nao estiver visivel, ele provavelmente esta na bandeja do sistema.",
            "DSW Painel Pro",
            0x00000040,
        )
    except Exception:
        print("DSW Painel Pro ja esta rodando.", file=sys.stderr)


def _write_startup_failure(exc: Exception) -> str:
    appdata = Path(os.getenv("APPDATA", ".")) / "DSW Painel Pro"
    appdata.mkdir(parents=True, exist_ok=True)
    log_path = appdata / "startup_error.log"
    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log_path.write_text(details, encoding="utf-8")
    return str(log_path)


def _show_startup_failure_message(log_path: str) -> None:
    text = (
        "Falha ao iniciar a interface do DSW Painel Pro.\n\n"
        "Verifique se o WebView2 do Windows esta instalado e se o build foi copiado por completo.\n"
        f"Log salvo em:\n{log_path}"
    )
    try:
        ctypes.windll.user32.MessageBoxW(0, text, "Erro ao iniciar DSW Painel Pro", 0x00000010)
    except Exception:
        print(text, file=sys.stderr)


if __name__ == "__main__":
    run()
