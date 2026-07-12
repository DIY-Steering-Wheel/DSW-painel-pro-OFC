from __future__ import annotations

import argparse
import ctypes
import importlib
import sys
import time
from pathlib import Path
from typing import Any

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
_TRAY_CONTROLLER = None


class TrayController:
    def __init__(self, window: webview.Window, api: NewAppApi, start_hidden: bool) -> None:
        self.window = window
        self.api = api
        self.start_hidden = start_hidden
        self.form = None
        self.notify_icon = None
        self.context_menu = None
        self._exit_requested = False

    @staticmethod
    def _import_winforms() -> Any:
        return importlib.import_module("System.Windows.Forms")

    @staticmethod
    def _import_drawing() -> Any:
        return importlib.import_module("System.Drawing")

    def install(self) -> None:
        try:
            from webview.platforms import winforms
            drawing = self._import_drawing()
            forms = self._import_winforms()

            form = None
            for _ in range(80):
                form = winforms.BrowserView.instances.get(self.window.uid)
                if form is not None:
                    break
                time.sleep(0.1)
            if form is None:
                return

            self.form = form
            self.notify_icon = forms.NotifyIcon()
            self.notify_icon.Text = "DSW Painel Pro"
            self.notify_icon.Icon = self._load_tray_icon(drawing)
            self.notify_icon.Visible = True

            menu = forms.ContextMenuStrip()
            self.context_menu = menu
            open_item = menu.Items.Add("Abrir DSW Painel Pro")
            exit_item = menu.Items.Add("Fechar DSW Painel Pro")
            open_item.Click += self._on_open_clicked
            exit_item.Click += self._on_exit_clicked
            self.notify_icon.ContextMenuStrip = menu
            self.notify_icon.DoubleClick += self._on_open_clicked
            form.Resize += self._on_form_resize
            form.FormClosed += self._on_form_closed
            form.Shown += self._on_form_shown

            if self.start_hidden and self._minimize_to_tray_enabled():
                self._hide_to_tray(show_tip=False, force_normal_state=True)
        except Exception:
            return

    def _on_form_shown(self, _sender, _args) -> None:
        _apply_windows_dark_titlebar(self.window)

    def _on_form_resize(self, _sender, _args) -> None:
        if self._exit_requested or self.form is None:
            return
        try:
            forms = self._import_winforms()

            if self.form.WindowState == forms.FormWindowState.Minimized and self._minimize_to_tray_enabled():
                self._hide_to_tray(show_tip=True)
        except Exception:
            return

    def _on_open_clicked(self, _sender, _args) -> None:
        self.restore_from_tray()

    def _on_exit_clicked(self, _sender, _args) -> None:
        self._exit_requested = True
        self._dispose_icon()
        try:
            if self.form is not None:
                self.form.Close()
            else:
                self.window.destroy()
        except Exception:
            return

    def _on_form_closed(self, _sender, _args) -> None:
        self._dispose_icon()

    def _hide_to_tray(self, show_tip: bool, force_normal_state: bool = False) -> None:
        if self.form is None:
            return
        try:
            forms = self._import_winforms()

            if force_normal_state:
                self.form.WindowState = forms.FormWindowState.Normal
            self.form.Hide()
            self.form.ShowInTaskbar = False
            if not force_normal_state:
                self.form.WindowState = forms.FormWindowState.Minimized
            if show_tip and self.notify_icon is not None:
                self.notify_icon.BalloonTipTitle = "DSW Painel Pro"
                self.notify_icon.BalloonTipText = "O aplicativo continua rodando na bandeja do sistema."
                self.notify_icon.ShowBalloonTip(2000)
        except Exception:
            return

    def restore_from_tray(self) -> None:
        if self.form is None:
            return
        try:
            forms = self._import_winforms()

            self.form.ShowInTaskbar = True
            self.form.Show()
            self.form.WindowState = forms.FormWindowState.Normal
            self.form.BringToFront()
            self.form.Activate()
        except Exception:
            return

    def _dispose_icon(self) -> None:
        if self.notify_icon is not None:
            try:
                self.notify_icon.Visible = False
                self.notify_icon.Dispose()
            except Exception:
                pass
            self.notify_icon = None
        self.context_menu = None

    def _load_tray_icon(self, drawing: Any) -> Any:
        icon_path = get_app_base_dir() / "app_icon.ico"
        if icon_path.exists():
            try:
                return drawing.Icon(str(icon_path))
            except Exception:
                pass
        try:
            return drawing.SystemIcons.Application
        except Exception:
            return None

    def _minimize_to_tray_enabled(self) -> bool:
        try:
            settings = self.api.bridge.store.load_settings()
            return settings.get("minimize_to_tray", True)
        except Exception:
            return True


def run() -> None:
    args = _parse_args()
    if not _ensure_single_instance():
        _show_already_running_message()
        return

    try:
        api = NewAppApi()
        base_dir = get_app_base_dir()
        start_in_tray = bool(args.tray)
        window = webview.create_window(
            APP_TITLE,
            url=(base_dir / "frontend" / "index.html").as_uri(),
            js_api=api,
            width=800,
            height=581,
            min_size=(1200, 648),
            resizable=False,
            hidden=start_in_tray,
            background_color="#111111",
        )
        webview.start(_bootstrap_windows_ui, args=(window, api, start_in_tray), debug=False)
    finally:
        _release_single_instance()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--tray", action="store_true")
    return parser.parse_args()


def _bootstrap_windows_ui(window: webview.Window, api: NewAppApi, start_in_tray: bool) -> None:
    global _TRAY_CONTROLLER
    tray = TrayController(window, api, start_in_tray)
    _TRAY_CONTROLLER = tray
    tray.install()
    _apply_windows_dark_titlebar(window, wait_for_show=not start_in_tray)


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


if __name__ == "__main__":
    run()
