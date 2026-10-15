"""Persistencia de configuración en config.json."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "scan_folder": "",
    "scan_dpi": 300,
    "scan_format": "PDF",
    "scan_color": "Color",
}

CONFIG_FILENAME = "config.json"


def _config_path(base_dir: Path) -> Path:
    return base_dir / CONFIG_FILENAME


def ensure_config(base_dir: Path) -> Path:
    path = _config_path(base_dir)
    if not path.exists():
        save_config(base_dir, dict(DEFAULT_CONFIG))
    return path


def load_config(base_dir: Path) -> dict[str, Any]:
    ensure_config(base_dir)
    path = _config_path(base_dir)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
        return merged
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("No se pudo leer config.json: %s. Usando valores predeterminados.", e)
        return dict(DEFAULT_CONFIG)


def save_config(base_dir: Path, config: dict[str, Any]) -> None:
    path = _config_path(base_dir)
    out = dict(DEFAULT_CONFIG)
    out.update({k: config[k] for k in DEFAULT_CONFIG if k in config})
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error("No se pudo guardar config.json: %s", e)
        raise


def reset_config(base_dir: Path) -> dict[str, Any]:
    save_config(base_dir, dict(DEFAULT_CONFIG))
    return dict(DEFAULT_CONFIG)
