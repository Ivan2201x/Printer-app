"""Fachada de impresión de archivos."""

from app.backends.print_common import PrintError
from app.platform import is_windows

if is_windows():
    from app.backends.print_win import print_file
else:
    from app.backends.print_linux import print_file

__all__ = ["PrintError", "print_file", "validate_print_file"]

from app.backends.print_common import validate_print_file  # noqa: E402
