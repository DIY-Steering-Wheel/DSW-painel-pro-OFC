from __future__ import annotations

import time
from typing import Any

try:
    import serial
    import serial.tools.list_ports
except Exception:  # pragma: no cover
    serial = None

try:
    from .config_store import ConfigStore
    from .constants import PANEL_FIELDS, PANEL_FIELDS_BY_KEY
except ImportError:  # pragma: no cover
    from config_store import ConfigStore
    from constants import PANEL_FIELDS, PANEL_FIELDS_BY_KEY


class PanelSender:
    def __init__(self, store: ConfigStore) -> None:
        self.store = store
        self._packets_sent = 0
        self._last_success_at = 0.0
        self._last_error = ""
        self._last_error_at = 0.0
        self._last_dispatch_at = 0.0

    def list_ports(self) -> list[str]:
        if serial is None:
            return []
        return [port.device for port in serial.tools.list_ports.comports()]

    def send(self, telemetry: dict[str, Any]) -> None:
        config = self.store.load_panel_config()
        if not self._can_dispatch(float(config.get("fps", 20))):
            return
        values = self.preview_values(telemetry)
        self._send_values(values, config)

    def send_defaults(self, force: bool = False) -> None:
        config = self.store.load_panel_config()
        if not force and not self._can_dispatch(float(config.get("fps", 20))):
            return
        values = self.preview_values({})
        self._send_values(values, config)

    def _send_values(self, values: list[Any], config: dict[str, Any]) -> None:
        port = config.get("port")
        if not port or serial is None:
            return
        if port not in self.list_ports():
            self._set_error(f"Porta {port} não encontrada.")
            return
        packet = ",".join(map(str, values)) + "\n"
        try:
            with serial.Serial(port=port, baudrate=115200, timeout=1) as conn:
                conn.write(packet.encode("utf-8"))
            self._packets_sent += 1
            self._last_success_at = time.time()
            self._last_error = ""
        except Exception as exc:
            self._set_error(str(exc))

    def preview_values(self, telemetry: dict[str, Any]) -> list[Any]:
        config = self.store.load_panel_config()
        settings = self.store.load_settings()
        fallback_overrides = settings.get("fallback_overrides", {})
        values = []
        for field_key in config["order"]:
            field = PANEL_FIELDS_BY_KEY[field_key]
            value = telemetry.get(field_key, fallback_overrides.get(field_key, field.default))
            values.append(self._normalize(value))
        return values

    def _normalize(self, value: Any) -> Any:
        if isinstance(value, bool):
            return 1 if value else 0
        if value is None:
            return 0
        if isinstance(value, float):
            return round(value, 3)
        return value

    def status(self, is_collecting: bool) -> dict[str, Any]:
        config = self.store.load_panel_config()
        port = config.get("port")
        ports = self.list_ports()
        return self._build_status(
            label="Painel serial",
            port=port,
            ports=ports,
            enabled=True,
            is_collecting=is_collecting,
        )

    def _build_status(
        self,
        *,
        label: str,
        port: str | None,
        ports: list[str],
        enabled: bool,
        is_collecting: bool,
    ) -> dict[str, Any]:
        now = time.time()
        if serial is None:
            state = "serial_unavailable"
            message = "PySerial não está disponível."
        elif not port:
            state = "not_configured"
            message = "Nenhuma porta serial configurada."
        elif port not in ports:
            state = "port_missing"
            message = f"Porta {port} não encontrada."
        elif not enabled:
            state = "disabled"
            message = "Envio desligado nas configurações."
        elif self._last_error and self._last_error_at >= self._last_success_at:
            state = "error"
            message = self._last_error
        elif not is_collecting:
            state = "ready"
            message = "Coleta parada. Porta pronta para novo envio."
        elif self._last_success_at:
            if is_collecting and now - self._last_success_at > 2.0:
                state = "waiting"
                message = "Aguardando novo envio de telemetria."
            else:
                state = "sending"
                message = "Comunicação serial OK."
        else:
            state = "ready"
            message = "Porta detectada, aguardando primeiro envio."
        return {
            "label": label,
            "port": port or "",
            "available": bool(port and port in ports),
            "enabled": enabled,
            "state": state,
            "message": message,
            "packets_sent": self._packets_sent,
            "last_success_at": self._format_timestamp(self._last_success_at),
            "last_error_at": self._format_timestamp(self._last_error_at),
        }

    def _set_error(self, text: str) -> None:
        self._last_error = text
        self._last_error_at = time.time()

    def _can_dispatch(self, fps: float) -> bool:
        now = time.perf_counter()
        interval = 1.0 / max(fps, 1.0)
        if self._last_dispatch_at and now - self._last_dispatch_at < interval:
            return False
        self._last_dispatch_at = now
        return True

    def _format_timestamp(self, value: float) -> str:
        if not value:
            return ""
        return time.strftime("%H:%M:%S", time.localtime(value))


class MotionSender:
    def __init__(self, store: ConfigStore) -> None:
        self.store = store
        self._packets_sent = 0
        self._last_success_at = 0.0
        self._last_error = ""
        self._last_error_at = 0.0
        self._last_dispatch_at = 0.0

    def send(self, telemetry: dict[str, Any]) -> None:
        config = self.store.load_motion_config()
        if not config.get("is_sending"):
            return
        if not self._can_dispatch(float(config.get("fps", 20))):
            return
        self._send_axes(telemetry, config)

    def send_defaults(self, force: bool = False) -> None:
        config = self.store.load_motion_config()
        if not config.get("is_sending"):
            return
        if not force and not self._can_dispatch(float(config.get("fps", 20))):
            return
        self._send_axes({}, config)

    def _send_axes(self, telemetry: dict[str, Any], config: dict[str, Any]) -> None:
        port = config.get("port")
        if not port or serial is None:
            return
        if port not in self.list_ports():
            self._set_error(f"Porta {port} não encontrada.")
            return
        x, y, z = self._normalize_axes(telemetry, config)
        packet = f"{x},{y},{z}\n"
        try:
            with serial.Serial(port=port, baudrate=int(config["baudrate"]), timeout=1) as conn:
                conn.write(packet.encode("utf-8"))
            self._packets_sent += 1
            self._last_success_at = time.time()
            self._last_error = ""
        except Exception as exc:
            self._set_error(str(exc))

    def list_ports(self) -> list[str]:
        if serial is None:
            return []
        return [port.device for port in serial.tools.list_ports.comports()]

    def preview(self, telemetry: dict[str, Any]) -> dict[str, dict[str, float]]:
        config = self.store.load_motion_config()
        x, y, z = self._normalize_axes(telemetry, config)
        return {
            "raw": {
                "x": float(telemetry.get("acceleration_x", 0) or 0),
                "y": float(telemetry.get("acceleration_y", 0) or 0),
                "z": float(telemetry.get("acceleration_z", 0) or 0),
            },
            "normalized": {"x": x, "y": y, "z": z},
        }

    def _normalize_axes(self, telemetry: dict[str, Any], config: dict[str, Any]) -> tuple[float, float, float]:
        minimum = float(config["min_value"])
        maximum = float(config["max_value"])
        axes = {
            "x": float(telemetry.get("acceleration_x", 0) or 0),
            "y": float(telemetry.get("acceleration_y", 0) or 0),
            "z": float(telemetry.get("acceleration_z", 0) or 0),
        }
        for axis in ("x", "y", "z"):
            if not config[f"onoff_invert_{axis}"]:
                axes[axis] = 0.0
            if config[f"phase_invert_{axis}"]:
                axes[axis] *= -1
            offset = float(config[f"offset_power_{axis}"])
            if offset > 0:
                axes[axis] *= 1 + offset
            elif offset < 0:
                axes[axis] /= 1 - offset
            axes[axis] = max(min(axes[axis], maximum), minimum)
            axes[axis] = round((axes[axis] - minimum) * 200 / (maximum - minimum) - 100, 3)
        return axes["x"], axes["y"], axes["z"]

    def status(self, is_collecting: bool) -> dict[str, Any]:
        config = self.store.load_motion_config()
        port = config.get("port")
        ports = self.list_ports()
        return self._build_status(
            label="Motion serial",
            port=port,
            ports=ports,
            enabled=bool(config.get("is_sending")),
            is_collecting=is_collecting,
        )

    def _build_status(
        self,
        *,
        label: str,
        port: str | None,
        ports: list[str],
        enabled: bool,
        is_collecting: bool,
    ) -> dict[str, Any]:
        now = time.time()
        if serial is None:
            state = "serial_unavailable"
            message = "PySerial não está disponível."
        elif not port:
            state = "not_configured"
            message = "Nenhuma porta serial configurada."
        elif port not in ports:
            state = "port_missing"
            message = f"Porta {port} não encontrada."
        elif not enabled:
            state = "disabled"
            message = "Envio desligado nas configurações."
        elif self._last_error and self._last_error_at >= self._last_success_at:
            state = "error"
            message = self._last_error
        elif not is_collecting:
            state = "ready"
            message = "Coleta parada. Porta pronta para novo envio."
        elif self._last_success_at:
            if is_collecting and now - self._last_success_at > 2.0:
                state = "waiting"
                message = "Aguardando novo envio de telemetria."
            else:
                state = "sending"
                message = "Comunicação serial OK."
        else:
            state = "ready"
            message = "Porta detectada, aguardando primeiro envio."
        return {
            "label": label,
            "port": port or "",
            "available": bool(port and port in ports),
            "enabled": enabled,
            "state": state,
            "message": message,
            "packets_sent": self._packets_sent,
            "last_success_at": self._format_timestamp(self._last_success_at),
            "last_error_at": self._format_timestamp(self._last_error_at),
        }

    def _set_error(self, text: str) -> None:
        self._last_error = text
        self._last_error_at = time.time()

    def _format_timestamp(self, value: float) -> str:
        if not value:
            return ""
        return time.strftime("%H:%M:%S", time.localtime(value))

    def _can_dispatch(self, fps: float) -> bool:
        now = time.perf_counter()
        interval = 1.0 / max(fps, 1.0)
        if self._last_dispatch_at and now - self._last_dispatch_at < interval:
            return False
        self._last_dispatch_at = now
        return True


def build_telemetry_rows(telemetry: dict[str, Any], allowed_keys: list[str] | None = None) -> list[dict[str, Any]]:
    if allowed_keys:
        fields = [PANEL_FIELDS_BY_KEY[key] for key in allowed_keys if key in PANEL_FIELDS_BY_KEY]
    else:
        fields = PANEL_FIELDS
    return [{"key": field.key, "label": field.label, "value": telemetry.get(field.key, field.default)} for field in fields]
