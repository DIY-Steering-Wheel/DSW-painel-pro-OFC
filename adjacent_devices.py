from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

try:
    import serial
    import serial.tools.list_ports
except Exception:  # pragma: no cover
    serial = None

LuaRuntime = None
for _lupa_module_name in (
    "lupa.lua55",
    "lupa.lua54",
    "lupa.lua53",
    "lupa.lua52",
    "lupa.lua51",
    "lupa.luajit21",
    "lupa.luajit20",
):
    try:
        _lupa_module = __import__(_lupa_module_name, fromlist=["LuaRuntime"])
        LuaRuntime = getattr(_lupa_module, "LuaRuntime", None)
        if LuaRuntime is not None:
            break
    except Exception:
        continue

if TYPE_CHECKING:
    try:
        from .config_store import ConfigStore
    except ImportError:  # pragma: no cover
        from config_store import ConfigStore


BLANK_SCRIPT = """exit = ""
-- Variaveis prontas:
-- speed, engine_rpm, brake, clutch, throttle, abs, acceleration_x, acceleration_y, acceleration_z
-- Tambem disponiveis em telemetry.speed, telemetry.engine_rpm, etc.
-- Helpers: clamp(v, min, max), map_range(v, in_min, in_max, out_min, out_max), bool_num(v), round(v)

exit = ""
"""

WIND_SIM_SCRIPT = """exit = ""
local vento = clamp(map_range(speed or 0, 0, 30, 0, 100), 0, 100)
exit = "WIND:" .. tostring(round(vento))
"""

CLUTCH_VIBRATION_SCRIPT = """exit = ""
local rpm = tonumber(engine_rpm) or 0
local intensidade = clamp(map_range(1000 - rpm, 0, 1000, 0, 100), 0, 100)
exit = "CLUTCH:" .. tostring(round(intensidade))
"""

BRAKE_ABS_SCRIPT = """exit = ""
local abs_ativo = bool_num(abs) > 0
local freio = clamp((tonumber(brake) or 0) * 100, 0, 100)
local intensidade = abs_ativo and freio or 0
exit = "BRAKE:" .. tostring(round(intensidade))
"""

ADJACENT_DEVICE_PRESETS: tuple[dict[str, str], ...] = (
    {
        "id": "custom",
        "name": "Custom",
        "description": "Script em branco para montar sua propria linha serial.",
        "script": BLANK_SCRIPT,
    },
    {
        "id": "wind_sim",
        "name": "Simulador de vento",
        "description": "Mapeia velocidade de 0 a 30 km/h para 0% a 100% e envia WIND:valor.",
        "script": WIND_SIM_SCRIPT,
    },
    {
        "id": "clutch_vibrator",
        "name": "Vibrador de embreagem",
        "description": "Quanto mais o RPM cai abaixo de 1000, maior a vibracao. Envia CLUTCH:valor.",
        "script": CLUTCH_VIBRATION_SCRIPT,
    },
    {
        "id": "brake_abs",
        "name": "Vibrador de freio ABS",
        "description": "Usa ABS e intensidade do freio para enviar BRAKE:valor.",
        "script": BRAKE_ABS_SCRIPT,
    },
)


def build_default_adjacent_devices() -> list[dict[str, Any]]:
    return [
        {
            "slot": 1,
            "enabled": False,
            "name": "Simulador de vento",
            "port": None,
            "baudrate": 115200,
            "fps": 20,
            "append_newline": True,
            "preset_id": "wind_sim",
            "script": WIND_SIM_SCRIPT,
        },
        {
            "slot": 2,
            "enabled": False,
            "name": "Vibrador embreagem",
            "port": None,
            "baudrate": 115200,
            "fps": 20,
            "append_newline": True,
            "preset_id": "clutch_vibrator",
            "script": CLUTCH_VIBRATION_SCRIPT,
        },
        {
            "slot": 3,
            "enabled": False,
            "name": "Vibrador freio ABS",
            "port": None,
            "baudrate": 115200,
            "fps": 20,
            "append_newline": True,
            "preset_id": "brake_abs",
            "script": BRAKE_ABS_SCRIPT,
        },
        {
            "slot": 4,
            "enabled": False,
            "name": "Dispositivo 4",
            "port": None,
            "baudrate": 115200,
            "fps": 20,
            "append_newline": True,
            "preset_id": "custom",
            "script": BLANK_SCRIPT,
        },
    ]


class AdjacentDevicesManager:
    def __init__(self, store: ConfigStore) -> None:
        self.store = store
        self._port_cache: tuple[float, list[str]] = (0.0, [])
        self._slot_state = [
            {
                "serial_conn": None,
                "serial_target": None,
                "packets_sent": 0,
                "last_success_at": 0.0,
                "last_error": "",
                "last_error_at": 0.0,
                "last_dispatch_at": 0.0,
                "compiled_script": None,
                "compiled_script_text": None,
                "lua_runtime": None,
            }
            for _ in range(4)
        ]

    def preset_catalog(self) -> list[dict[str, str]]:
        return [dict(item) for item in ADJACENT_DEVICE_PRESETS]

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

    def validate_configs(self, configs: list[dict[str, Any]]) -> None:
        if LuaRuntime is None:
            raise RuntimeError("Lua indisponivel no app. Instale a runtime Lua antes de salvar os dispositivos adjacentes.")
        for index, config in enumerate(configs[:4], start=1):
            if not config.get("enabled"):
                continue
            script = str(config.get("script", "") or "").strip()
            if not script:
                raise RuntimeError(f"Dispositivo adjacente {index}: o script Lua nao pode ficar vazio quando o envio estiver ligado.")
            self._compile_script(index - 1, script)

    def send(self, telemetry: dict[str, Any], is_collecting: bool) -> None:
        configs = self.store.load_settings().get("adjacent_devices", [])
        for slot_index in range(4):
            config = configs[slot_index] if slot_index < len(configs) else {}
            if not is_collecting or not config.get("enabled"):
                self._close_slot(slot_index)
                continue
            if not self._can_dispatch(slot_index, float(config.get("fps", 20))):
                continue
            self._send_slot(slot_index, config, telemetry)

    def send_command(self, slot_index: int, command: str) -> None:
        configs = self.store.load_settings().get("adjacent_devices", [])
        if slot_index < 0 or slot_index >= len(configs):
            raise RuntimeError("Dispositivo adjacente invalido.")
        config = configs[slot_index]
        if not config.get("enabled"):
            raise RuntimeError("Dispositivo adjacente esta desligado.")
        payload = str(command or "").strip()
        if not payload:
            raise RuntimeError("Digite um comando antes de enviar.")
        self._write_payload(slot_index, config, payload)

    def status_list(self, is_collecting: bool) -> list[dict[str, Any]]:
        configs = self.store.load_settings().get("adjacent_devices", [])
        ports = self.list_ports()
        items: list[dict[str, Any]] = []
        for slot_index in range(4):
            config = configs[slot_index] if slot_index < len(configs) else {}
            state = self._slot_state[slot_index]
            port = config.get("port")
            enabled = bool(config.get("enabled", False))
            if LuaRuntime is None:
                status_name = "lua_unavailable"
                message = "Runtime Lua indisponivel."
            elif serial is None:
                status_name = "serial_unavailable"
                message = "PySerial nao esta disponivel."
            elif not port:
                status_name = "not_configured"
                message = "Nenhuma porta serial configurada."
            elif port not in ports:
                status_name = "port_missing"
                message = f"Porta {port} nao encontrada."
            elif not enabled:
                status_name = "disabled"
                message = "Envio desligado nas configuracoes."
            elif state["last_error"] and state["last_error_at"] >= state["last_success_at"]:
                status_name = "error"
                message = state["last_error"]
            elif not is_collecting:
                status_name = "ready"
                message = "Coleta parada. Porta pronta para novo envio."
            elif state["last_success_at"]:
                if time.time() - state["last_success_at"] > 2.0:
                    status_name = "waiting"
                    message = "Aguardando novo envio de telemetria."
                else:
                    status_name = "sending"
                    message = "Comunicacao serial OK."
            else:
                status_name = "ready"
                message = "Porta detectada, aguardando primeiro envio."
            items.append(
                {
                    "kind": f"adjacent:{slot_index + 1}",
                    "slot": slot_index + 1,
                    "label": str(config.get("name") or f"Adjacente {slot_index + 1}"),
                    "port": port or "",
                    "available": bool(port and port in ports),
                    "enabled": enabled,
                    "connected": bool(port and port in ports and enabled and serial is not None and LuaRuntime is not None),
                    "state": status_name,
                    "message": message,
                    "baudrate": int(config.get("baudrate", 115200) or 115200),
                    "mode": "Lua",
                    "packets_sent": state["packets_sent"],
                    "last_success_at": self._format_timestamp(state["last_success_at"]),
                    "last_error_at": self._format_timestamp(state["last_error_at"]),
                }
            )
        return items

    def shutdown(self) -> None:
        for slot_index in range(4):
            self._close_slot(slot_index)

    def _send_slot(self, slot_index: int, config: dict[str, Any], telemetry: dict[str, Any]) -> None:
        script = str(config.get("script", "") or "").strip()
        if not script:
            self._set_error(slot_index, "Script Lua vazio.")
            self._close_slot(slot_index)
            return
        port = config.get("port")
        if not port or serial is None:
            self._close_slot(slot_index)
            return
        if port not in self.list_ports():
            self._set_error(slot_index, f"Porta {port} nao encontrada.")
            self._close_slot(slot_index)
            return
        try:
            runner = self._compile_script(slot_index, script)
            payload = self._normalize_exit_value(runner(self._build_lua_env(slot_index, telemetry)))
            if not payload:
                return
            self._write_payload(slot_index, config, payload)
        except Exception as exc:
            self._set_error(slot_index, f"Falha no script Lua: {exc}")
            self._close_slot(slot_index)

    def _write_payload(self, slot_index: int, config: dict[str, Any], payload: str) -> None:
        port = config.get("port")
        if not port or serial is None:
            raise RuntimeError("Nenhuma porta serial configurada.")
        if port not in self.list_ports():
            self._close_slot(slot_index)
            raise RuntimeError(f"Porta {port} nao encontrada.")
        packet = self._compose_packet(payload, bool(config.get("append_newline", True)))
        try:
            conn = self._ensure_serial(slot_index, port, int(config.get("baudrate", 115200)))
            conn.write(packet.encode("ascii"))
            state = self._slot_state[slot_index]
            state["packets_sent"] += 1
            state["last_success_at"] = time.time()
            state["last_error"] = ""
        except UnicodeEncodeError as exc:
            self._set_error(slot_index, str(exc))
            raise RuntimeError("O script Lua precisa gerar somente caracteres ASCII simples para o dispositivo adjacente.") from exc
        except Exception as exc:
            self._close_slot(slot_index)
            self._set_error(slot_index, str(exc))
            raise

    def _compile_script(self, slot_index: int, script: str):
        state = self._slot_state[slot_index]
        if state["compiled_script"] is not None and state["compiled_script_text"] == script:
            return state["compiled_script"]
        if LuaRuntime is None:
            raise RuntimeError("Runtime Lua indisponivel.")
        runtime = LuaRuntime(unpack_returned_tuples=True)
        chunk = 'return function(env)\nlocal _ENV = env\nlocal exit = ""\n' + script + "\nreturn exit\nend"
        try:
            compiled = runtime.execute(chunk)
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        state["lua_runtime"] = runtime
        state["compiled_script"] = compiled
        state["compiled_script_text"] = script
        return compiled

    def _build_lua_env(self, slot_index: int, telemetry: dict[str, Any]):
        runtime = self._slot_state[slot_index]["lua_runtime"]
        env = runtime.table() if runtime is not None else {}
        telemetry_table = runtime.table() if runtime is not None else {}
        for key, value in telemetry.items():
            telemetry_table[key] = value
            env[key] = value
        env["telemetry"] = telemetry_table
        env["math"] = runtime.globals().math
        env["string"] = runtime.globals().string
        env["table"] = runtime.globals().table
        env["tonumber"] = runtime.globals().tonumber
        env["tostring"] = runtime.globals().tostring
        env["type"] = runtime.globals().type
        env["pairs"] = runtime.globals().pairs
        env["ipairs"] = runtime.globals().ipairs
        env["clamp"] = self._lua_clamp
        env["map_range"] = self._lua_map_range
        env["bool_num"] = self._lua_bool_num
        env["round"] = self._lua_round
        return env

    def _ensure_serial(self, slot_index: int, port: str, baudrate: int):
        state = self._slot_state[slot_index]
        target = (port, baudrate)
        conn = state["serial_conn"]
        if conn is not None and getattr(conn, "is_open", False) and state["serial_target"] == target:
            return conn
        self._close_slot(slot_index)
        state["serial_conn"] = serial.Serial(port=port, baudrate=baudrate, timeout=1, write_timeout=1)
        state["serial_target"] = target
        return state["serial_conn"]

    def _close_slot(self, slot_index: int) -> None:
        state = self._slot_state[slot_index]
        conn = state["serial_conn"]
        state["serial_conn"] = None
        state["serial_target"] = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def _set_error(self, slot_index: int, text: str) -> None:
        state = self._slot_state[slot_index]
        state["last_error"] = text
        state["last_error_at"] = time.time()

    def _can_dispatch(self, slot_index: int, fps: float) -> bool:
        state = self._slot_state[slot_index]
        now = time.perf_counter()
        interval = 1.0 / max(fps, 1.0)
        if state["last_dispatch_at"] and now - state["last_dispatch_at"] < interval:
            return False
        state["last_dispatch_at"] = now
        return True

    def _format_timestamp(self, value: float) -> str:
        if not value:
            return ""
        return time.strftime("%H:%M:%S", time.localtime(value))

    def _compose_packet(self, payload: str, append_newline: bool) -> str:
        packet = str(payload).rstrip("\r\n")
        return packet + ("\n" if append_newline else "")

    def _normalize_exit_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            rounded = round(float(value))
            return str(int(rounded) if abs(float(value) - rounded) < 1e-9 else float(value))
        return str(value).strip()

    def _lua_clamp(self, value: Any, minimum: Any, maximum: Any) -> float:
        numeric = self._to_float(value)
        minimum_value = self._to_float(minimum)
        maximum_value = self._to_float(maximum)
        return max(minimum_value, min(maximum_value, numeric))

    def _lua_map_range(self, value: Any, in_min: Any, in_max: Any, out_min: Any, out_max: Any) -> float:
        source_value = self._to_float(value)
        source_min = self._to_float(in_min)
        source_max = self._to_float(in_max)
        target_min = self._to_float(out_min)
        target_max = self._to_float(out_max)
        if abs(source_max - source_min) < 1e-9:
            return target_min
        ratio = (source_value - source_min) / (source_max - source_min)
        return target_min + (target_max - target_min) * ratio

    def _lua_bool_num(self, value: Any) -> int:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return 1
            if normalized in {"0", "false", "no", "off", ""}:
                return 0
        return 1 if bool(value) else 0

    def _lua_round(self, value: Any) -> int:
        return int(round(self._to_float(value)))

    def _to_float(self, value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0
