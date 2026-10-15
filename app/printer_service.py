"""Fachada de impresoras (Windows / Linux)."""

from app.platform import is_windows
from app.printer_models import PrintJobInfo, PrinterInfo

if is_windows():
    from app.backends.printer_win import (  # noqa: F401
        cancel_job,
        get_default_printer,
        get_printer_status,
        list_print_jobs,
        list_printers,
        pause_job,
        resume_job,
        set_default_printer,
    )
else:
    from app.backends.printer_linux import (  # noqa: F401
        cancel_job,
        get_default_printer,
        get_printer_status,
        list_print_jobs,
        list_printers,
        pause_job,
        resume_job,
        set_default_printer,
    )

__all__ = [
    "PrinterInfo",
    "PrintJobInfo",
    "list_printers",
    "get_default_printer",
    "set_default_printer",
    "get_printer_status",
    "list_print_jobs",
    "cancel_job",
    "pause_job",
    "resume_job",
]
