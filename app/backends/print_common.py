"""Validación común de impresión."""

from pathlib import Path

from app.utils import is_printable_file


class PrintError(Exception):
    pass


def validate_print_file(path: Path) -> None:
    if not path.exists():
        raise PrintError("El archivo no existe.")
    if not is_printable_file(path):
        raise PrintError("Tipo de archivo no soportado. Use PDF, TXT, PNG, JPG o JPEG.")
