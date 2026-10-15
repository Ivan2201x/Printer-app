"""Impresión de archivos — Windows."""

import logging
import os
from pathlib import Path

import win32api

from app.backends.print_common import PrintError, validate_print_file

logger = logging.getLogger(__name__)


def print_file(path: Path, printer_name: str, copies: int = 1) -> None:
    validate_print_file(path)
    copies = max(1, min(copies, 99))
    abs_path = str(path.resolve())
    params = f'"{printer_name}"'
    for _ in range(copies):
        try:
            rc = win32api.ShellExecute(
                0, "printto", abs_path, params, os.path.dirname(abs_path) or ".", 0
            )
        except OSError as e:
            logger.error("ShellExecute: %s", e)
            raise PrintError("No fue posible enviar el documento a la impresora.") from e
        if rc <= 32:
            raise PrintError(f"No fue posible enviar el documento (código {rc}).")
