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


class _SerialPortMixin:
    def __init__(self) -> None:
        self._port_cache: tuple[float, list[str]] = (0.0, [])
        self._serial_conn = None
        self._serial_target: tuple[str, int] | None = None

    def list_ports(self) -> list[str]:
        if serial is None:
            return []
        now = time.monotonic()
        cached_at, cached_ports = self._port_cache
        if now - cached_at < 1.0:
            return list(cached_ports)
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self._port_cache = (now, ports)
        return list(ports)

    def _ensure_serial(self, port: str, baudrate: int):
        target = (port, baudrate)
        conn = self._serial_conn
        if conn is not None and getattr(conn, "is_open", False) and self._serial_target == target:
            return conn
        self._close_serial()
        self._serial_conn = serial.Serial(port=port, baudrate=baudrate, timeout=1, write_timeout=1)
        self._serial_target = target
        return self._serial_conn

    def _close_serial(self) -> None:
        conn = self._serial_conn
        self._serial_conn = None
        self._serial_target = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def shutdown(self) -> None:
        self._close_serial()


class PanelSender(_SerialPortMixin):
    def __init__(self, store: ConfigStore) -> None:
        super().__init__()
        self.store = store
        self._packets_sent = 0
        self._printed_first_packet = False
        self._last_success_at = 0.0
        self._last_error = ""
        self._last_error_at = 0.0
        self._last_dispatch_at = 0.0

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
        if config.get("mode") == "Disabled":
            self._close_serial()
            return
        port = config.get("port")
        if not port or serial is None:
            self._close_serial()
            return
        if port not in self.list_ports():
            self._set_error(f"Porta {port} nao encontrada.")
            self._close_serial()
            return
        packet = self._build_packet(values, bool(config.get("append_newline", True)))
        try:
            conn = self._ensure_serial(port, int(config.get("baudrate", 115200)))
            conn.write(self._encode_packet(packet))
        #    print(f"[Painel serial] {packet.rstrip()}",port)
            self._print_first_packet(packet)
            self._packets_sent += 1
            self._last_success_at = time.time()
            self._last_error = ""
        except Exception as exc:
            self._close_serial()
            self._set_error(str(exc))

    def send_command(self, command: str) -> None:
        text = str(command or "")
        if not text.strip():
            return
        config = self.store.load_panel_config()
        if config.get("mode") == "Disabled":
            raise RuntimeError("Painel serial esta desligado.")
        self._write_packet(config, text)

    def preview_values(self, telemetry: dict[str, Any]) -> list[Any]:
        config = self.store.load_panel_config()
        settings = self.store.load_settings()
        fallback_overrides = settings.get("fallback_overrides", {})
        values = []
        for field_key in config["order"]:
            field = PANEL_FIELDS_BY_KEY[field_key]
            value = telemetry.get(field_key, fallback_overrides.get(field_key, field.default))
            values.append(self._normalize_panel_value(value))
        return values

    def _normalize_panel_value(self, value: Any) -> int:
        return self._to_wire_int(value)

    def _to_wire_int(self, value: Any) -> int:
        if isinstance(value, bool):
            return 1 if value else 0
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(round(float(value)))
        try:
            return int(round(float(str(value).strip().replace(",", "."))))
        except Exception:
            return 0

    def status(self, is_collecting: bool) -> dict[str, Any]:
        config = self.store.load_panel_config()
        port = config.get("port")
        ports = self.list_ports()
        return self._build_status(
            label="Painel serial",
            port=port,
            ports=ports,
            enabled=config.get("mode") != "Disabled",
            is_collecting=is_collecting,
            baudrate=int(config.get("baudrate", 115200)),
            mode=str(config.get("mode", "Automatic")),
        )

    def _build_status(
        self,
        *,
        label: str,
        port: str | None,
        ports: list[str],
        enabled: bool,
        is_collecting: bool,
        baudrate: int,
        mode: str,
    ) -> dict[str, Any]:
        now = time.time()
        if serial is None:
            state = "serial_unavailable"
            message = "PySerial nao esta disponivel."
        elif not port:
            state = "not_configured"
            message = "Nenhuma porta serial configurada."
        elif port not in ports:
            state = "port_missing"
            message = f"Porta {port} nao encontrada."
        elif not enabled:
            state = "disabled"
            message = "Envio desligado nas configuracoes."
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
                message = "Comunicacao serial OK."
        else:
            state = "ready"
            message = "Porta detectada, aguardando primeiro envio."
        return {
            "label": label,
            "port": port or "",
            "available": bool(port and port in ports),
            "enabled": enabled,
            "connected": bool(port and port in ports and enabled and serial is not None),
            "state": state,
            "message": message,
            "baudrate": baudrate,
            "mode": mode,
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

    def _print_first_packet(self, packet: str) -> None:
        if self._printed_first_packet:
            return
        print(f"[Painel serial] {packet.rstrip()}")
        self._printed_first_packet = True

    def _build_packet(self, values: list[Any], append_newline: bool) -> str:
        return self._compose_packet(",".join(map(str, values)), append_newline)

    def _write_packet(self, config: dict[str, Any], payload: str) -> None:
        port = config.get("port")
        if not port or serial is None:
            raise RuntimeError("Nenhuma porta serial configurada.")
        if port not in self.list_ports():
            self._close_serial()
            raise RuntimeError(f"Porta {port} nao encontrada.")
        packet = self._compose_packet(payload, bool(config.get("append_newline", True)))
        try:
            conn = self._ensure_serial(port, int(config.get("baudrate", 115200)))
            conn.write(self._encode_packet(packet))
            self._print_first_packet(packet)
            self._packets_sent += 1
            self._last_success_at = time.time()
            self._last_error = ""
        except UnicodeEncodeError as exc:
            self._set_error(str(exc))
            raise RuntimeError("O comando manual precisa usar somente caracteres ASCII simples para o Arduino.") from exc
        except Exception as exc:
            self._close_serial()
            self._set_error(str(exc))
            raise

    def _compose_packet(self, payload: str, append_newline: bool) -> str:
        packet = str(payload).rstrip("\r\n")
        return packet + ("\n" if append_newline else "")

    def _encode_packet(self, payload: str) -> bytes:
        return payload.encode("ascii")


class MotionSender(_SerialPortMixin):
    def __init__(self, store: ConfigStore) -> None:
        super().__init__()
        self.store = store
        self._packets_sent = 0
        self._printed_first_packet = False
        self._last_success_at = 0.0
        self._last_error = ""
        self._last_error_at = 0.0
        self._last_dispatch_at = 0.0

    def send(self, telemetry: dict[str, Any]) -> None:
        config = self.store.load_motion_config()
        if config.get("mode") == "Disabled" or not config.get("is_sending"):
            self._close_serial()
            return
        if not self._can_dispatch(float(config.get("fps", 20))):
            return
        self._send_axes(telemetry, config)

    def send_defaults(self, force: bool = False) -> None:
        config = self.store.load_motion_config()
        if config.get("mode") == "Disabled" or not config.get("is_sending"):
            self._close_serial()
            return
        if not force and not self._can_dispatch(float(config.get("fps", 20))):
            return
        self._send_axes({}, config)

    def _send_axes(self, telemetry: dict[str, Any], config: dict[str, Any]) -> None:
        port = config.get("port")
        if not port or serial is None:
            self._close_serial()
            return
        if port not in self.list_ports():
            self._set_error(f"Porta {port} nao encontrada.")
            self._close_serial()
            return
        x, y, z = self._normalize_axes(telemetry, config)
        packet = self._compose_packet(
            ",".join((str(self._to_wire_int(x)), str(self._to_wire_int(y)), str(self._to_wire_int(z)))),
            bool(config.get("append_newline", True)),
        )
        try:
            conn = self._ensure_serial(port, int(config["baudrate"]))
            conn.write(self._encode_packet(packet))
            self._print_first_packet(packet)
            self._packets_sent += 1
            self._last_success_at = time.time()
            self._last_error = ""
        except Exception as exc:
            self._close_serial()
            self._set_error(str(exc))

    def send_command(self, command: str) -> None:
        text = str(command or "")
        if not text.strip():
            return
        config = self.store.load_motion_config()
        if config.get("mode") == "Disabled":
            raise RuntimeError("Motion serial esta desligado.")
        port = config.get("port")
        if not port or serial is None:
            raise RuntimeError("Nenhuma porta serial configurada.")
        if port not in self.list_ports():
            self._close_serial()
            raise RuntimeError(f"Porta {port} nao encontrada.")
        packet = self._compose_packet(text, bool(config.get("append_newline", True)))
        try:
            conn = self._ensure_serial(port, int(config["baudrate"]))
            conn.write(self._encode_packet(packet))
            self._print_first_packet(packet)
            self._packets_sent += 1
            self._last_success_at = time.time()
            self._last_error = ""
        except UnicodeEncodeError as exc:
            self._set_error(str(exc))
            raise RuntimeError("O comando manual precisa usar somente caracteres ASCII simples para o motion/Arduino.") from exc
        except Exception as exc:
            self._close_serial()
            self._set_error(str(exc))
            raise

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
            enabled=bool(config.get("is_sending")) and config.get("mode") != "Disabled",
            is_collecting=is_collecting,
            baudrate=int(config.get("baudrate", 115200)),
            mode=str(config.get("mode", "Disabled")),
        )

    def _build_status(
        self,
        *,
        label: str,
        port: str | None,
        ports: list[str],
        enabled: bool,
        is_collecting: bool,
        baudrate: int,
        mode: str,
    ) -> dict[str, Any]:
        now = time.time()
        if serial is None:
            state = "serial_unavailable"
            message = "PySerial nao esta disponivel."
        elif not port:
            state = "not_configured"
            message = "Nenhuma porta serial configurada."
        elif port not in ports:
            state = "port_missing"
            message = f"Porta {port} nao encontrada."
        elif not enabled:
            state = "disabled"
            message = "Envio desligado nas configuracoes."
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
                message = "Comunicacao serial OK."
        else:
            state = "ready"
            message = "Porta detectada, aguardando primeiro envio."
        return {
            "label": label,
            "port": port or "",
            "available": bool(port and port in ports),
            "enabled": enabled,
            "connected": bool(port and port in ports and enabled and serial is not None),
            "state": state,
            "message": message,
            "baudrate": baudrate,
            "mode": mode,
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

    def _print_first_packet(self, packet: str) -> None:
        if self._printed_first_packet:
            return
        print(f"[Motion serial] {packet.rstrip()}")
        self._printed_first_packet = True

    def _compose_packet(self, payload: str, append_newline: bool) -> str:
        packet = str(payload).rstrip("\r\n")
        return packet + ("\n" if append_newline else "")

    def _encode_packet(self, payload: str) -> bytes:
        return payload.encode("ascii")

    def _can_dispatch(self, fps: float) -> bool:
        now = time.perf_counter()
        interval = 1.0 / max(fps, 1.0)
        if self._last_dispatch_at and now - self._last_dispatch_at < interval:
            return False
        self._last_dispatch_at = now
        return True

    def _to_wire_int(self, value: Any) -> int:
        if isinstance(value, bool):
            return 1 if value else 0
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(round(float(value)))
        try:
            return int(round(float(str(value).strip().replace(",", "."))))
        except Exception:
            return 0


def build_telemetry_rows(telemetry: dict[str, Any], allowed_keys: list[str] | None = None) -> list[dict[str, Any]]:
    if allowed_keys:
        rows: list[dict[str, Any]] = []
        for key in allowed_keys:
            field = PANEL_FIELDS_BY_KEY.get(key)
            if field is None:
                rows.append({"key": key, "label": key.replace("_", " ").title(), "value": telemetry.get(key, 0)})
            else:
                rows.append({"key": field.key, "label": field.label, "value": telemetry.get(field.key, field.default)})
        return rows
    return [{"key": field.key, "label": field.label, "value": telemetry.get(field.key, field.default)} for field in PANEL_FIELDS]
