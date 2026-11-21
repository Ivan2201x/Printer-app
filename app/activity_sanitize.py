"""Minimización y enmascaramiento para monitoreo de actividad (sin contraseñas)."""

from __future__ import annotations

import re
from typing import Any

# Campos / contextos que nunca deben registrar texto literal.
SENSITIVE_NAME_PARTS = (
    "password",
    "passwd",
    "pass",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
    "pin",
    "cvv",
    "ssn",
    "tel_key",
)

# Etiquetas de aplicación externa (solo referencia; hook OS no implementado).
EXCLUDED_EXTERNAL_APPS = (
    "chrome",
    "firefox",
    "msedge",
    "outlook",
    "teams",
    "1password",
    "keepass",
)

MASK = "***"
MAX_LITERAL_LEN = 32


def _name_hints(widget: Any) -> str:
    parts: list[str] = []
    for attr in ("_name", "name"):
        v = getattr(widget, attr, None)
        if v:
            parts.append(str(v).lower())
    tv = getattr(widget, "cget", None)
    if callable(tv):
        try:
            parts.append(str(widget.cget("textvariable")).lower())
        except Exception:
            pass
    return " ".join(parts)


def is_password_entry(widget: Any) -> bool:
    show = getattr(widget, "cget", None)
    if callable(show):
        try:
            if widget.cget("show") in ("*", "•", "●"):
                return True
        except Exception:
            pass
    if getattr(widget, "_activity_sensitive", False):
        return True
    hints = _name_hints(widget)
    return any(p in hints for p in SENSITIVE_NAME_PARTS)


def is_sensitive_context(*, widget: Any | None = None, field_name: str = "", module: str = "") -> bool:
    blob = f"{field_name} {module} {_name_hints(widget) if widget else ''}".lower()
    return any(p in blob for p in SENSITIVE_NAME_PARTS)


def mask_text(text: str) -> str:
    if not text:
        return ""
    if len(text) <= 2:
        return MASK
    return text[0] + MASK + text[-1]


def sanitize_literal(text: str, *, allowed: bool) -> str | None:
    """Devuelve None si no debe almacenarse; enmascarado si allowed."""
    if not allowed or not text:
        return None
    cleaned = text.replace("\n", " ").replace("\r", " ")
    if len(cleaned) > MAX_LITERAL_LEN:
        cleaned = cleaned[:MAX_LITERAL_LEN] + "…"
    return mask_text(cleaned)


def format_shortcut(keysym: str, state: int) -> str:
    """Atajo sin carácter literal (métrica)."""
    parts: list[str] = []
    # Tk state bits
    if state & 0x0004:
        parts.append("Ctrl")
    if state & 0x0008:
        parts.append("Alt")
    if state & 0x0001:
        parts.append("Shift")
    key = (keysym or "").replace("Control_", "Ctrl+").replace("Alt_", "Alt+")
    if key in ("Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R"):
        return "+".join(parts) if parts else key
    parts.append(key)
    return "+".join(parts)


def looks_like_password_payload(text: str) -> bool:
    """Heurística para pruebas y defensa en profundidad."""
    if not text or len(text) < 6:
        return False
    if re.search(r"(?i)(password|passwd|secret|token|api[_-]?key)", text):
        return True
    # Secuencia larga sin espacios — posible credencial
    if len(text) >= 12 and " " not in text and text.isascii():
        upper = sum(1 for c in text if c.isupper())
        lower = sum(1 for c in text if c.islower())
        digit = sum(1 for c in text if c.isdigit())
        if upper and lower and digit:
            return True
    return False


def redact_for_log(record: dict[str, Any]) -> dict[str, Any]:
    """Elimina campos de texto si son sensibles (para assert en tests)."""
    out = dict(record)
    for key in ("literal_sample", "text", "content", "keystrokes"):
        val = out.get(key)
        if isinstance(val, str) and (looks_like_password_payload(val) or is_sensitive_context(field_name=key)):
            out[key] = None
    return out
