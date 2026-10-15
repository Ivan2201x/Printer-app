"""Fachada de escaneo (WIA / SANE)."""

from app.platform import is_windows
from app.scanner_models import ScannerDevice, ScannerError

if is_windows():
    from app.backends.scanner_win import list_scanners, scan_to_temp_file
else:
    from app.backends.scanner_linux import list_scanners, scan_to_temp_file

__all__ = ["ScannerError", "ScannerDevice", "list_scanners", "scan_to_temp_file"]
