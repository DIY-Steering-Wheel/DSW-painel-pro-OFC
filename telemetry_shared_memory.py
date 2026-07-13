from __future__ import annotations

import json
import mmap
import struct
import sys
import time
from typing import Any


class TelemetrySharedMemoryService:
    def __init__(self, map_name: str = "Local\\DSWPainelProTelemetry", max_size: int = 65536) -> None:
        self.map_name = map_name
        self.max_size = max(4096, int(max_size))
        self._buffer: mmap.mmap | None = None
        self._last_error = ""
        self._last_bytes = 0
        self._last_updated_at = 0.0
        self._supported = sys.platform.startswith("win")
        if self._supported:
            self._ensure_buffer()

    def publish(self, payload: dict[str, Any]) -> None:
        if not self._supported:
            return
        try:
            buffer = self._ensure_buffer()
            data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(data) + 4 > self.max_size:
                trimmed = {
                    "selected_game": payload.get("selected_game"),
                    "is_collecting": payload.get("is_collecting"),
                    "status_text": payload.get("status_text"),
                    "telemetry": payload.get("telemetry", {}),
                    "updated_at": payload.get("updated_at"),
                }
                data = json.dumps(trimmed, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(data) + 4 > self.max_size:
                raise RuntimeError("Payload excede o tamanho maximo da memoria compartilhada.")

            buffer.seek(0)
            buffer.write(struct.pack("<I", len(data)))
            buffer.write(data)
            remaining = self.max_size - 4 - len(data)
            if remaining > 0:
                buffer.write(b"\x00" * remaining)
            buffer.flush()
            self._last_bytes = len(data)
            self._last_updated_at = time.time()
            self._last_error = ""
        except Exception as exc:
            self._last_error = str(exc)

    def status(self) -> dict[str, Any]:
        return {
            "supported": self._supported,
            "available": self._buffer is not None,
            "map_name": self.map_name,
            "max_size": self.max_size,
            "last_bytes": self._last_bytes,
            "last_updated_at": self._format_timestamp(self._last_updated_at),
            "last_error": self._last_error,
        }

    def shutdown(self) -> None:
        buffer = self._buffer
        self._buffer = None
        if buffer is not None:
            try:
                buffer.close()
            except Exception:
                pass

    def _ensure_buffer(self) -> mmap.mmap:
        if self._buffer is not None:
            return self._buffer
        self._buffer = mmap.mmap(-1, self.max_size, tagname=self.map_name, access=mmap.ACCESS_WRITE)
        return self._buffer

    def _format_timestamp(self, value: float) -> str:
        if not value:
            return ""
        return time.strftime("%H:%M:%S", time.localtime(value))
