"""Telemetría empresarial: metadata, historial, cola offline y envío HTTPS JSON."""

from __future__ import annotations

import json
import logging
import socket
import ssl
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app import __version__

logger = logging.getLogger(__name__)

QUEUE_NAME = "telemetry_queue.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_device_id(config: dict[str, Any]) -> str:
    did = (config.get("device_id") or "").strip()
    if did:
        return did
    did = str(uuid.uuid4())
    config["device_id"] = did
    return did


def collect_device_snapshot(base_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    import platform
    import getpass

    device_id = ensure_device_id(config)
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except OSError:
        local_ip = "—"

    public_ip = _fetch_public_ip() if config.get("telemetry_include_public_ip", True) else "—"

    snap = {
        "device_id": device_id,
        "hostname": hostname,
        "username": getpass.getuser(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor() or "—",
        "python_version": platform.python_version(),
        "app_version": __version__,
        "local_ip": local_ip,
        "public_ip": public_ip,
        "mac_address": _format_mac(uuid.getnode()),
        "enterprise_tag": config.get("enterprise_tag", ""),
        "timestamp_utc": _utc_now(),
    }
    try:
        from app.printer_service import list_printers
        from app.scanner_service import list_scanners

        snap["printers_count"] = len(list_printers())
        snap["scanners_count"] = len(list_scanners())
    except Exception as e:
        logger.debug("Conteo dispositivos telemetría: %s", e)
        snap["printers_count"] = None
        snap["scanners_count"] = None
    return snap


def _format_mac(node: int) -> str:
    if (node >> 40) % 2:
        return "—"
    parts = [f"{(node >> shift) & 0xFF:02x}" for shift in range(40, -1, -8)]
    return ":".join(parts)


def _fetch_public_ip(timeout: float = 4.0) -> str:
    url = "https://api.ipify.org?format=json"
    try:
        with urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return str(data.get("ip", "—"))
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError, OSError) as e:
        logger.debug("public_ip: %s", e)
        return "—"


class TelemetryClient:
    """Cola local + envío al API (sin bloquear UI)."""

    def __init__(self, base_dir: Path, get_config) -> None:
        self.base_dir = base_dir
        self.get_config = get_config
        self.queue_path = base_dir / "logs" / QUEUE_NAME
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="telemetry")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.flush()

    def _loop(self) -> None:
        last_heartbeat = 0.0
        while not self._stop.wait(5):
            cfg = self.get_config()
            if not cfg.get("telemetry_enabled"):
                continue
            self.flush()
            interval = max(60, int(cfg.get("telemetry_interval_sec", 300)))
            now = time.time()
            if now - last_heartbeat >= interval:
                last_heartbeat = now
                self.record(
                    "heartbeat",
                    {"snapshot": collect_device_snapshot(self.base_dir, cfg)},
                )

    def record(self, event_type: str, payload: dict[str, Any]) -> None:
        cfg = self.get_config()
        if not cfg.get("telemetry_enabled"):
            return
        event = {
            "type": event_type,
            "timestamp_utc": _utc_now(),
            "device_id": ensure_device_id(cfg),
            "payload": payload,
        }
        with self._lock:
            self.queue_path.parent.mkdir(parents=True, exist_ok=True)
            with self.queue_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def record_print(
        self,
        *,
        printer: str,
        file_path: Path,
        copies: int,
        success: bool,
        error: str | None = None,
    ) -> None:
        self.record(
            "print",
            {
                "printer": printer,
                "file_name": file_path.name,
                "file_path": str(file_path.resolve()),
                "file_size": file_path.stat().st_size if file_path.is_file() else None,
                "copies": copies,
                "success": success,
                "error": error,
            },
        )

    def record_scan(self, *, saved_path: Path, fmt: str, pages: int, upload: bool) -> None:
        payload = {
            "saved_path": str(saved_path.resolve()),
            "file_name": saved_path.name,
            "format": fmt,
            "pages": pages,
            "file_size": saved_path.stat().st_size if saved_path.is_file() else None,
        }
        self.record("scan", payload)
        if upload and saved_path.is_file():
            cfg = self.get_config()
            meta = {**payload, "device_id": ensure_device_id(cfg)}
            self._upload_scan_file(saved_path, meta)

    def flush(self) -> None:
        cfg = self.get_config()
        if not cfg.get("telemetry_enabled"):
            return
        url = (cfg.get("telemetry_api_url") or "").rstrip("/")
        key = cfg.get("telemetry_api_key") or ""
        if not url or not key:
            return

        with self._lock:
            if not self.queue_path.is_file():
                return
            lines = self.queue_path.read_text(encoding="utf-8").splitlines()
            if not lines:
                return
            events = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            if not events:
                return

        body = json.dumps({"events": events}, ensure_ascii=False).encode("utf-8")
        endpoint = f"{url}/api/v1/events"
        req = Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": key,
            },
        )
        try:
            ctx = ssl.create_default_context()
            with urlopen(req, timeout=30, context=ctx) as resp:
                if 200 <= resp.status < 300:
                    with self._lock:
                        self.queue_path.write_text("", encoding="utf-8")
                    logger.info("Telemetría: %s eventos enviados", len(events))
        except HTTPError as e:
            logger.warning("Telemetría HTTP %s: %s", e.code, e.reason)
        except (URLError, OSError, TimeoutError) as e:
            logger.warning("Telemetría sin conexión: %s", e)

    def _upload_scan_file(self, path: Path, meta: dict[str, Any]) -> None:
        cfg = self.get_config()
        url = (cfg.get("telemetry_api_url") or "").rstrip("/")
        key = cfg.get("telemetry_api_key") or ""
        if not url or not key:
            return
        try:
            import mimetypes

            boundary = uuid.uuid4().hex
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            file_bytes = path.read_bytes()
            meta_json = json.dumps(meta, ensure_ascii=False).encode("utf-8")
            parts = [
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="metadata"\r\n\r\n',
                meta_json,
                b"\r\n",
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode(),
                f"Content-Type: {mime}\r\n\r\n".encode(),
                file_bytes,
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
            body = b"".join(parts)
            req = Request(
                f"{url}/api/v1/scans/upload",
                data=body,
                method="POST",
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "X-API-Key": key,
                },
            )
            ctx = ssl.create_default_context()
            with urlopen(req, timeout=120, context=ctx) as resp:
                if 200 <= resp.status < 300:
                    logger.info("Escaneo subido al servidor: %s", path.name)
        except Exception as e:
            logger.warning("No se pudo subir escaneo: %s", e)
