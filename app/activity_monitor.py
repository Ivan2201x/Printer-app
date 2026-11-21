"""Monitoreo de actividad in-app: métricas, atajos, sin hook global de SO (por defecto)."""

from __future__ import annotations

import getpass
import logging
import socket
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

from app.activity_sanitize import (
    format_shortcut,
    is_password_entry,
    is_sensitive_context,
    sanitize_literal,
)
from app.telemetry_service import TelemetryClient, _utc_now, ensure_device_id

logger = logging.getLogger(__name__)

CONSENT_VERSION = "1.0"
FLUSH_INTERVAL_SEC = 60


@dataclass
class ModuleMetrics:
    key_press_count: int = 0
    shortcuts: Counter = field(default_factory=Counter)
    literal_samples: list[str] = field(default_factory=list)


class ActivityMonitor:
    """
    Registra métricas de teclado solo dentro de esta aplicación.
    Hook a nivel OS: NO implementado — ver docs/ACTIVITY_MONITORING.md.
    """

    def __init__(
        self,
        root,
        get_config: Callable[[], dict[str, Any]],
        telemetry: TelemetryClient,
        get_module: Callable[[], str],
    ) -> None:
        self.root = root
        self.get_config = get_config
        self.telemetry = telemetry
        self.get_module = get_module
        self._metrics: dict[str, ModuleMetrics] = {}
        self._lock = threading.Lock()
        self._server_enabled = True
        self._bound = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def corporate_user_id(self) -> str:
        cfg = self.get_config()
        tag = (cfg.get("enterprise_tag") or "").strip()
        user = getpass.getuser()
        host = socket.gethostname()
        base = f"{user}@{host}"
        return f"{tag}:{base}" if tag else base

    def is_active(self) -> bool:
        cfg = self.get_config()
        if not cfg.get("activity_monitor_enabled"):
            return False
        if not cfg.get("activity_consent_acknowledged"):
            return False
        if cfg.get("activity_consent_version") != CONSENT_VERSION:
            return False
        if not cfg.get("telemetry_enabled"):
            return False
        if not self._server_enabled:
            return False
        return True

    def set_server_policy(self, enabled: bool) -> None:
        self._server_enabled = enabled

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._ensure_bindings()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="activity-monitor")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.flush()

    def _ensure_bindings(self) -> None:
        if self._bound:
            return
        self.root.bind_class("Entry", "<KeyPress>", self._on_key, add="+")
        self.root.bind_class("CTkEntry", "<KeyPress>", self._on_key, add="+")
        self.root.bind_all("<KeyPress>", self._on_key, add="+")
        self._bound = True

    def _on_key(self, event) -> None:
        if not self.is_active():
            return
        widget = event.widget
        module = self.get_module() or "app"
        with self._lock:
            m = self._metrics.setdefault(module, ModuleMetrics())
            m.key_press_count += 1
            shortcut = format_shortcut(getattr(event, "keysym", ""), getattr(event, "state", 0))
            if any(x in shortcut for x in ("Ctrl", "Alt", "F1", "F2", "F3", "F4", "F5", "Tab", "Return")):
                m.shortcuts[shortcut] += 1
            cfg = self.get_config()
            if cfg.get("activity_capture_text") and not is_password_entry(widget):
                if not is_sensitive_context(widget=widget, module=module):
                    ch = getattr(event, "char", "") or ""
                    if ch and ch.isprintable():
                        sample = sanitize_literal(ch, allowed=True)
                        if sample and len(m.literal_samples) < 5:
                            m.literal_samples.append(sample)

    def flush(self) -> None:
        if not self.is_active():
            return
        with self._lock:
            if not self._metrics:
                return
            snapshot = {}
            for mod, data in self._metrics.items():
                snapshot[mod] = {
                    "key_press_count": data.key_press_count,
                    "shortcuts": dict(data.shortcuts.most_common(20)),
                    "literal_samples": list(data.literal_samples),
                }
            self._metrics.clear()

        cfg = self.get_config()
        self.telemetry.record(
            "activity_metrics",
            {
                "corporate_user_id": self.corporate_user_id(),
                "device_id": ensure_device_id(cfg),
                "window_module": self.get_module(),
                "modules": snapshot,
                "metrics_only": not cfg.get("activity_capture_text"),
                "timestamp_utc": _utc_now(),
            },
        )
        self.telemetry.flush()

    def _loop(self) -> None:
        last_policy = 0.0
        last_flush = 0.0
        while not self._stop.wait(2):
            if not self.is_active():
                continue
            now = time.time()
            if now - last_flush >= FLUSH_INTERVAL_SEC:
                last_flush = now
                self.flush()
            if now - last_policy >= 120:
                last_policy = now
                self._fetch_server_policy()

    def _fetch_server_policy(self) -> None:
        cfg = self.get_config()
        url = (cfg.get("telemetry_api_url") or "").rstrip("/")
        key = cfg.get("telemetry_api_key") or ""
        if not url or not key:
            return
        try:
            import json
            import ssl
            from urllib.request import Request, urlopen

            req = Request(
                f"{url}/api/v1/activity/policy",
                headers={"X-API-Key": key},
            )
            ctx = ssl.create_default_context()
            with urlopen(req, timeout=8, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self._server_enabled = bool(data.get("monitoring_enabled", True))
        except Exception as e:
            logger.debug("Política actividad: %s", e)


def try_os_global_hook() -> None:
    """
    Captura global del SO — NO IMPLEMENTADA.

    Requiere aprobación explícita de la empresa tras leer docs/ACTIVITY_MONITORING.md
    sección «Riesgos hook global».
    """
    raise NotImplementedError(
        "Hook global de teclado deshabilitado por diseño. "
        "Solo monitoreo dentro de esta aplicación hasta aprobación formal."
    )
