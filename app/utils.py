"""Utilidades compartidas."""

import os
import re
from datetime import datetime
from pathlib import Path

PRINTABLE_EXTENSIONS = {".pdf", ".txt", ".png", ".jpg", ".jpeg"}

DPI_OPTIONS = [100, 150, 200, 300, 600]
COLOR_MODES = ("Color", "Escala de grises", "Blanco y negro")
OUTPUT_FORMATS = ("JPG", "PNG", "PDF")


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def safe_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name.strip())
    return cleaned or "scan"


def default_scan_name(ext: str = "pdf") -> str:
    ext = ext.lower().lstrip(".")
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"scan_{ts}.{ext}"


def file_type_label(path: Path) -> str:
    ext = path.suffix.lower()
    mapping = {
        ".pdf": "PDF",
        ".txt": "Texto",
        ".png": "PNG",
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
    }
    return mapping.get(ext, ext.upper().lstrip(".") or "Desconocido")


def is_printable_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in PRINTABLE_EXTENSIONS


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_bytes(size: int | None) -> str:
    if size is None or size < 0:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def unique_path(path: Path) -> Path:
    """Si path existe, prueba path con _1, _2, ... antes de la extensión."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    parent = path.parent
    n = 1
    while n < 10_000:
        candidate = parent / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1
    raise OSError(f"No hay nombre libre para {path.name}")


def expand_user_path(folder: str) -> Path:
    if not folder:
        return Path.home() / "Documents" / "Escaneos"
    return Path(os.path.expandvars(os.path.expanduser(folder)))
