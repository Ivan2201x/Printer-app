"""Impresión de archivos — Linux (CUPS lp)."""

import logging
from pathlib import Path

from app.backends.print_common import PrintError, validate_print_file
from app.backends.subprocess_util import run

logger = logging.getLogger(__name__)


def print_file(path: Path, printer_name: str, copies: int = 1) -> None:
    validate_print_file(path)
    copies = max(1, min(copies, 99))
    args = ["lp", "-d", printer_name, "-n", str(copies), str(path.resolve())]
    cp = run(args, timeout=120)
    if cp.returncode != 0:
        err = (cp.stderr or cp.stdout or "").strip()
        logger.error("lp: %s", err)
        raise PrintError("No fue posible enviar el documento a la impresora.")
