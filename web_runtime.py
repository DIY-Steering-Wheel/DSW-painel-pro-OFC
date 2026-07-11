from __future__ import annotations

import base64
import io
import json
import shutil
import socket
import tempfile
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

try:
    import qrcode
except Exception:  # pragma: no cover
    qrcode = None

try:
    from .config_store import ConfigStore
    from .runtime_paths import get_app_base_dir
except ImportError:  # pragma: no cover
    from config_store import ConfigStore
    from runtime_paths import get_app_base_dir


class WebRuntimeService:
    def __init__(self, store: ConfigStore, payload_provider: Callable[[], dict[str, Any]]) -> None:
        self.store = store
        self.payload_provider = payload_provider
        self.base_dir = get_app_base_dir()
        self.templates_dir = self.base_dir / "web" / "templates"
        self._http_server: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._udp_thread: threading.Thread | None = None
        self._udp_stop = threading.Event()
        self._udp_socket: socket.socket | None = None
        self._last_error = ""
        self._udp_messages: deque[dict[str, Any]] = deque(maxlen=10)
        self._udp_packets = 0
        self._ensure_default_template()

    def status(self) -> dict[str, Any]:
        settings = self.store.load_settings()
        web_config = settings.get("web_server", {})
        templates = self.load_template_catalog()
        selected_template = self._normalize_template_id(web_config.get("selected_template", "simple-dashboard"), templates)
        http_port = int(web_config.get("http_port", 8080))
        udp_port = int(web_config.get("udp_port", 28000))
        local_ip = self._get_local_ip()
        network_url = f"http://{local_ip}:{http_port}"
        selected_meta = next((item for item in templates if item["id"] == selected_template), None)
        return {
            "http_enabled": self._http_server is not None,
            "http_host": web_config.get("http_host", "0.0.0.0"),
            "http_port": http_port,
            "http_url": f"http://localhost:{http_port}",
            "network_ip": local_ip,
            "network_url": network_url,
            "qr_data_url": self._build_qr_data_url(network_url) if self._http_server is not None else "",
            "qr_available": qrcode is not None,
            "selected_template": selected_template,
            "selected_template_name": (selected_meta or {}).get("name", "Sem template"),
            "templates": templates,
            "udp_enabled": self._udp_thread is not None and self._udp_thread.is_alive(),
            "udp_host": web_config.get("udp_host", "0.0.0.0"),
            "udp_port": udp_port,
            "udp_packets": self._udp_packets,
            "udp_messages": list(self._udp_messages),
            "api_endpoints": self._api_endpoints(),
            "last_error": self._last_error,
        }

    def save_config(self, data: dict[str, Any]) -> dict[str, Any]:
        settings = self.store.load_settings()
        web_config = dict(settings.get("web_server", {}))
        web_config.update(data)
        web_config["selected_template"] = self._normalize_template_id(
            web_config.get("selected_template", "simple-dashboard"),
            self.load_template_catalog(),
        )
        settings = self.store.save_settings({"web_server": web_config})
        return settings["web_server"]

    def load_template_catalog(self) -> list[dict[str, Any]]:
        self._ensure_default_template()
        items: list[dict[str, Any]] = []
        if not self.templates_dir.exists():
            return items

        for template_dir in sorted(path for path in self.templates_dir.iterdir() if path.is_dir()):
            manifest_path = template_dir / "manifest.json"
            index_path = template_dir / "index.html"
            if not manifest_path.exists() or not index_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            template_id = manifest.get("id") or template_dir.name
            preview_path = (manifest.get("preview") or "").strip()
            preview_uri = ""
            if preview_path:
                resolved_preview = (template_dir / preview_path).resolve()
                if resolved_preview.exists():
                    preview_uri = resolved_preview.as_uri()
            built_in = template_dir.name == "simple-dashboard" or template_id == "simple-dashboard"
            items.append(
                {
                    "id": template_id,
                    "name": manifest.get("name") or template_dir.name.replace("-", " ").title(),
                    "description": manifest.get("description", "Template para navegador e celular."),
                    "author": manifest.get("author", "Autor desconhecido"),
                    "version": manifest.get("version", "1.0.0"),
                    "entry_html": manifest.get("entry_html", "index.html"),
                    "supports_mobile": bool(manifest.get("supports_mobile", True)),
                    "preview_uri": preview_uri,
                    "folder": template_dir.name,
                    "built_in": built_in,
                    "can_delete": not built_in,
                    "website_label": manifest.get("website_label", "Link do criador"),
                    "website_url": (manifest.get("website_url") or "").strip(),
                }
            )
        return items

    def import_template_archive(self, source_path: str) -> list[str]:
        if not source_path:
            raise RuntimeError("Selecione um arquivo ZIP antes de importar.")

        source = Path(source_path)
        if not source.exists():
            raise RuntimeError("O arquivo ZIP informado não existe mais.")
        if source.suffix.lower() != ".zip":
            raise RuntimeError("Use um arquivo ZIP com o template HTML.")

        self.templates_dir.mkdir(parents=True, exist_ok=True)
        current_templates = self.load_template_catalog()
        existing_folders = {item["folder"] for item in current_templates}
        existing_ids = {item["id"] for item in current_templates}

        with tempfile.TemporaryDirectory(prefix="dsw_template_import_") as temp_dir:
            staging_root = Path(temp_dir)
            shutil.unpack_archive(str(source), str(staging_root))
            template_dirs = self._discover_template_dirs(staging_root)
            if not template_dirs:
                raise RuntimeError("Nenhum template válido foi encontrado no ZIP.")

            imported_names: list[str] = []
            for template_dir in template_dirs:
                manifest_path = template_dir / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                template_id = manifest.get("id") or template_dir.name
                folder_name = template_dir.name
                if folder_name in existing_folders:
                    raise RuntimeError(f"Já existe um template na pasta '{folder_name}'.")
                if template_id in existing_ids:
                    raise RuntimeError(f"Já existe um template com id '{template_id}'.")
                manifest["built_in"] = False
                target_dir = self.templates_dir / folder_name
                shutil.copytree(template_dir, target_dir)
                (target_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                imported_names.append(manifest.get("name") or folder_name)
                existing_folders.add(folder_name)
                existing_ids.add(template_id)
        return imported_names

    def delete_template(self, template_id: str) -> str:
        templates = self.load_template_catalog()
        template = next((item for item in templates if item["id"] == template_id), None)
        if template is None:
            raise RuntimeError("Template não encontrado.")
        if template.get("built_in"):
            raise RuntimeError("O template padrão não pode ser excluído.")

        target = self.templates_dir / template["folder"]
        if target.exists():
            shutil.rmtree(target)

        remaining = [item for item in self.load_template_catalog() if item["id"] != template_id]
        settings = self.store.load_settings()
        web_config = dict(settings.get("web_server", {}))
        if web_config.get("selected_template") == template_id:
            web_config["selected_template"] = remaining[0]["id"] if remaining else "simple-dashboard"
            self.store.save_settings({"web_server": web_config})
        return template["name"]

    def start_http(self) -> dict[str, Any]:
        if self._http_server is not None:
            return self.status()

        config = self.store.load_settings().get("web_server", {})
        host = config.get("http_host", "0.0.0.0")
        port = int(config.get("http_port", 8080))
        service = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                service._handle_http_get(self)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

        try:
            self._http_server = ThreadingHTTPServer((host, port), Handler)
        except OSError as exc:
            self._http_server = None
            self._last_error = f"Falha ao iniciar servidor web: {exc}"
            raise RuntimeError(self._last_error) from exc

        self._http_thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
        self._http_thread.start()
        self.save_config({"http_enabled": True})
        self._last_error = ""
        return self.status()

    def stop_http(self) -> dict[str, Any]:
        if self._http_server is not None:
            self._http_server.shutdown()
            self._http_server.server_close()
            self._http_server = None
            self._http_thread = None
        self.save_config({"http_enabled": False})
        return self.status()

    def start_udp(self) -> dict[str, Any]:
        if self._udp_thread is not None and self._udp_thread.is_alive():
            return self.status()
        config = self.store.load_settings().get("web_server", {})
        host = config.get("udp_host", "0.0.0.0")
        port = int(config.get("udp_port", 28000))
        self._udp_stop.clear()
        self._udp_packets = 0
        self._udp_messages.clear()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((host, port))
            sock.settimeout(0.5)
        except OSError as exc:
            self._last_error = f"Falha ao iniciar servidor UDP: {exc}"
            raise RuntimeError(self._last_error) from exc

        def run() -> None:
            try:
                with sock:
                    self._udp_socket = sock
                    while not self._udp_stop.is_set():
                        try:
                            payload, address = sock.recvfrom(4096)
                        except socket.timeout:
                            continue
                        text = payload.decode("utf-8", errors="replace")
                        self._udp_packets += 1
                        self._udp_messages.appendleft(
                            {
                                "from": f"{address[0]}:{address[1]}",
                                "payload": text[:200],
                                "received_at": time.strftime("%H:%M:%S"),
                            }
                        )
                        response = json.dumps(self._udp_payload(), ensure_ascii=False).encode("utf-8")
                        sock.sendto(response, address)
            except OSError as exc:
                self._last_error = f"Falha no servidor UDP: {exc}"
            finally:
                self._udp_socket = None

        self._udp_thread = threading.Thread(target=run, daemon=True)
        self._udp_thread.start()
        self.save_config({"udp_enabled": True})
        self._last_error = ""
        return self.status()

    def stop_udp(self) -> dict[str, Any]:
        self._udp_stop.set()
        if self._udp_socket is not None:
            try:
                self._udp_socket.close()
            except OSError:
                pass
        self._udp_thread = None
        self.save_config({"udp_enabled": False})
        return self.status()

    def _handle_http_get(self, handler: BaseHTTPRequestHandler) -> None:
        path = urlparse(handler.path).path
        payload = self.payload_provider()

        if path == "/api/health":
            self._json(handler, {"ok": True, "service": "dsw-painel-pro", "time": time.time()})
            return
        if path == "/api/state":
            self._json(handler, payload)
            return
        if path == "/api/all":
            self._json(handler, self._full_api_payload(payload))
            return
        if path == "/api/telemetry":
            self._json(
                handler,
                {
                    "selected_game": payload.get("selected_game"),
                    "status_text": payload.get("status_text"),
                    "is_collecting": payload.get("is_collecting"),
                    "telemetry_rows": payload.get("telemetry_rows", []),
                },
            )
            return
        if path == "/api/panel-values":
            self._json(handler, payload.get("panel_preview", {}))
            return
        if path == "/api/motion-preview":
            self._json(handler, payload.get("motion_preview", {}))
            return
        if path == "/api/games":
            self._json(
                handler,
                {
                    "selected_game": payload.get("selected_game"),
                    "games": payload.get("games", []),
                    "install_modal": payload.get("install_modal", {}),
                },
            )
            return
        if path == "/api/devices":
            self._json(handler, payload.get("device_status", {}))
            return
        if path == "/api/config":
            self._json(
                handler,
                {
                    "basic_settings": payload.get("basic_settings", {}),
                    "panel_config": payload.get("panel_config", {}),
                    "motion_config": payload.get("motion_config", {}),
                    "web_server": payload.get("web_server", {}),
                    "available_ports": payload.get("available_ports", []),
                },
            )
            return
        if path == "/api/capabilities":
            self._json(handler, self._capabilities_payload())
            return
        if path == "/api/web-server":
            self._json(handler, self.status())
            return

        template_file = self._resolve_template_file(path)
        if template_file is not None and template_file.exists():
            data = template_file.read_bytes()
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", self._content_type(template_file.suffix.lower()))
            handler.send_header("Content-Length", str(len(data)))
            handler.end_headers()
            handler.wfile.write(data)
            return

        self._json(handler, {"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def _resolve_template_file(self, path: str) -> Path | None:
        template_root = self._selected_template_root()
        if template_root is None or not template_root.exists():
            return None

        template_meta = next(
            (item for item in self.load_template_catalog() if item["folder"] == template_root.name),
            None,
        )
        entry_html = (template_meta or {}).get("entry_html", "index.html")
        relative_path = entry_html if path in {"/", "/index.html"} else unquote(path.lstrip("/"))
        requested = (template_root / relative_path).resolve()
        if template_root.resolve() not in requested.parents and requested != template_root.resolve():
            return None
        return requested if requested.is_file() else None

    def _selected_template_root(self) -> Path | None:
        templates = self.load_template_catalog()
        if not templates:
            return None
        config = self.store.load_settings().get("web_server", {})
        selected_template = self._normalize_template_id(config.get("selected_template", "simple-dashboard"), templates)
        selected = next((item for item in templates if item["id"] == selected_template), templates[0])
        return self.templates_dir / selected["folder"]

    def _normalize_template_id(self, template_id: str, templates: list[dict[str, Any]]) -> str:
        if templates and any(item["id"] == template_id for item in templates):
            return template_id
        return templates[0]["id"] if templates else "simple-dashboard"

    def _json(self, handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def _content_type(self, suffix: str) -> str:
        return {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "application/octet-stream")

    def _get_local_ip(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except OSError:
            try:
                return socket.gethostbyname(socket.gethostname())
            except OSError:
                return "127.0.0.1"

    def _build_qr_data_url(self, value: str) -> str:
        try:
            if qrcode is None:
                return ""
            image = qrcode.make(value)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            return f"data:image/png;base64,{encoded}"
        except Exception:
            return ""

    def build_pix_donation_qr(self, pix_key: str, *, name: str, city: str) -> str:
        payload = self._pix_payload(pix_key.strip(), name=name, city=city)
        return self._build_qr_data_url(payload) if payload else ""

    def _pix_payload(self, pix_key: str, *, name: str, city: str) -> str:
        if not pix_key:
            return ""

        def field(tag: str, value: str) -> str:
            return f"{tag}{len(value):02d}{value}"

        merchant_account = (
            field("00", "BR.GOV.BCB.PIX")
            + field("01", pix_key)
            + field("02", "DSW Simuladores")
        )
        payload = (
            field("00", "01")
            + field("26", merchant_account)
            + field("52", "0000")
            + field("53", "986")
            + field("58", "BR")
            + field("59", name[:25])
            + field("60", city[:15])
            + field("62", field("05", "***"))
            + "6304"
        )
        return payload + self._crc16(payload)

    def _crc16(self, payload: str) -> str:
        crc = 0xFFFF
        for char in payload:
            crc ^= ord(char) << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
        return f"{crc:04X}"

    def _api_endpoints(self) -> list[dict[str, str]]:
        return [
            {"path": "/api/health", "description": "Status simples do serviço."},
            {"path": "/api/state", "description": "Estado completo atual do aplicativo."},
            {"path": "/api/all", "description": "Estado completo com capacidades da API."},
            {"path": "/api/telemetry", "description": "Somente telemetria em tempo real."},
            {"path": "/api/panel-values", "description": "Valores ordenados da saída do painel."},
            {"path": "/api/motion-preview", "description": "Preview bruto e normalizado do motion."},
            {"path": "/api/games", "description": "Lista de jogos e dados do instalador."},
            {"path": "/api/devices", "description": "Status das conexões seriais do painel e motion."},
            {"path": "/api/config", "description": "Configurações atuais do app."},
            {"path": "/api/capabilities", "description": "Recursos e superfícies expostas."},
            {"path": "/api/web-server", "description": "Estado do servidor web e UDP."},
        ]

    def _capabilities_payload(self) -> dict[str, Any]:
        return {
            "ok": True,
            "service": "dsw-painel-pro",
            "http_endpoints": self._api_endpoints(),
            "udp_response": {
                "format": "json",
                "includes": [
                    "meta",
                    "state",
                    "games",
                    "devices",
                    "panel_preview",
                    "motion_preview",
                    "web_server",
                ],
            },
            "template_management": {
                "import_zip": True,
                "activate": True,
                "delete": True,
                "default_template": "simple-dashboard",
            },
        }

    def _full_api_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "meta": {
                "service": "dsw-painel-pro",
                "generated_at": time.time(),
                "api_version": 1,
            },
            "capabilities": self._capabilities_payload(),
            "state": payload,
        }

    def _udp_payload(self) -> dict[str, Any]:
        payload = self.payload_provider()
        return {
            "ok": True,
            "meta": {
                "service": "dsw-painel-pro",
                "generated_at": time.time(),
                "transport": "udp",
            },
            "games": payload.get("games", []),
            "devices": payload.get("device_status", {}),
            "panel_preview": payload.get("panel_preview", {}),
            "motion_preview": payload.get("motion_preview", {}),
            "state": payload,
            "web_server": self.status(),
        }

    def _discover_template_dirs(self, root: Path) -> list[Path]:
        candidates: list[Path] = []
        if self._is_valid_template_dir(root):
            candidates.append(root)
        for manifest_path in root.rglob("manifest.json"):
            parent = manifest_path.parent
            if self._is_valid_template_dir(parent) and parent not in candidates:
                candidates.append(parent)
        return sorted(candidates, key=lambda item: len(item.parts))

    def _is_valid_template_dir(self, path: Path) -> bool:
        return (path / "manifest.json").exists() and (path / "index.html").exists()

    def _ensure_default_template(self) -> None:
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        template_dir = self.templates_dir / "simple-dashboard"
        template_dir.mkdir(parents=True, exist_ok=True)

        files: dict[str, str] = {
            "manifest.json": json.dumps(
                {
                    "id": "simple-dashboard",
                    "name": "Simple Dashboard",
                    "description": "Template padrão com telemetria ao vivo, status do jogo e valores principais.",
                    "author": "DSW Painel Pro",
                    "version": "1.0.0",
                    "entry_html": "index.html",
                    "supports_mobile": True,
                    "built_in": True,
                    "website_label": "Documentação",
                    "website_url": "",
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            "index.html": """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DSW Dashboard</title>
  <link rel="stylesheet" href="./styles.css">
</head>
<body>
  <main class="dashboard">
    <section class="hero">
      <div>
        <p class="eyebrow">DSW Painel Pro</p>
        <h1 id="gameName">Aguardando jogo</h1>
        <p id="gameState">Sem coleta ativa</p>
      </div>
      <span id="collectChip" class="chip">Offline</span>
    </section>
    <section class="grid">
      <article class="card">
        <h2>Velocidade</h2>
        <strong id="speedValue">0</strong>
      </article>
      <article class="card">
        <h2>RPM</h2>
        <strong id="rpmValue">0</strong>
      </article>
      <article class="card">
        <h2>Marcha</h2>
        <strong id="gearValue">0</strong>
      </article>
      <article class="card">
        <h2>Temperatura</h2>
        <strong id="tempValue">0</strong>
      </article>
    </section>
    <section class="list-card">
      <div class="list-head">
        <h2>Telemetria ao vivo</h2>
        <span id="updatedAt">--:--:--</span>
      </div>
      <div id="telemetryList" class="telemetry-list"></div>
    </section>
  </main>
  <script src="./app.js"></script>
</body>
</html>
""",
            "styles.css": """:root {
  color-scheme: dark;
  --bg: #09121d;
  --bg-2: #0f1d2d;
  --card: rgba(255, 255, 255, 0.06);
  --line: rgba(255, 255, 255, 0.1);
  --text: #eef5ff;
  --muted: #9db1cb;
  --accent: #74c0ff;
  --accent-2: #7dffbe;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  font-family: "Segoe UI", Tahoma, sans-serif;
  color: var(--text);
  background:
    radial-gradient(circle at top left, rgba(116, 192, 255, 0.2), transparent 28%),
    linear-gradient(160deg, var(--bg), var(--bg-2));
}
.dashboard {
  width: min(1100px, calc(100vw - 24px));
  margin: 0 auto;
  padding: 18px 0 28px;
  display: grid;
  gap: 16px;
}
.hero, .card, .list-card {
  border: 1px solid var(--line);
  border-radius: 24px;
  background: var(--card);
  backdrop-filter: blur(10px);
}
.hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 20px;
}
.eyebrow {
  margin: 0 0 6px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--muted);
}
h1, h2, p { margin: 0; }
h1 { font-size: clamp(28px, 6vw, 48px); }
#gameState { margin-top: 8px; color: var(--muted); }
.chip {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(116, 192, 255, 0.16);
  color: var(--accent);
}
.grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.card {
  padding: 16px;
  display: grid;
  gap: 10px;
}
.card h2 {
  font-size: 14px;
  color: var(--muted);
}
.card strong {
  font-size: clamp(26px, 5vw, 40px);
}
.list-card {
  padding: 18px;
  display: grid;
  gap: 14px;
}
.list-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
#updatedAt {
  color: var(--muted);
  font-size: 14px;
}
.telemetry-list {
  display: grid;
  gap: 10px;
}
.row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.05);
}
.label { color: var(--muted); }
@media (max-width: 760px) {
  .dashboard { width: min(100vw - 16px, 1100px); padding-top: 12px; }
  .hero { flex-direction: column; align-items: flex-start; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
""",
            "app.js": """const fields = {
  speed: document.getElementById("speedValue"),
  engine_rpm: document.getElementById("rpmValue"),
  current_gear: document.getElementById("gearValue"),
  water_temperature: document.getElementById("tempValue"),
};

async function loadState() {
  try {
    const response = await fetch("/api/state");
    const data = await response.json();
    render(data);
  } catch (error) {
    console.error(error);
  }
}

function render(data) {
  document.getElementById("gameName").textContent = data.selected_game || "Aguardando jogo";
  document.getElementById("gameState").textContent = data.status_text || "Sem coleta ativa";
  document.getElementById("collectChip").textContent = data.is_collecting ? "Coletando" : "Offline";
  document.getElementById("updatedAt").textContent = new Date().toLocaleTimeString("pt-BR");

  const values = Object.fromEntries((data.telemetry_rows || []).map((row) => [row.key, row.value]));
  Object.entries(fields).forEach(([key, node]) => {
    node.textContent = values[key] ?? 0;
  });

  const list = document.getElementById("telemetryList");
  list.innerHTML = "";
  (data.telemetry_rows || []).slice(0, 12).forEach((row) => {
    const item = document.createElement("div");
    item.className = "row";
    item.innerHTML = `<span class="label">${row.label}</span><strong>${row.value}</strong>`;
    list.appendChild(item);
  });
}

loadState();
setInterval(loadState, 500);
""",
        }

        for name, content in files.items():
            target = template_dir / name
            if not target.exists():
                target.write_text(content, encoding="utf-8")
