"""Impresoras y cola — Windows (win32print)."""

import logging

import win32print

from app.printer_models import PrintJobInfo, PrinterInfo

logger = logging.getLogger(__name__)


def _printer_status_flags() -> dict[int, str]:
    pairs = [
        ("PRINTER_STATUS_PAUSED", "Pausada"),
        ("PRINTER_STATUS_ERROR", "Error"),
        ("PRINTER_STATUS_OFFLINE", "Offline"),
        ("PRINTER_STATUS_PRINTING", "Imprimiendo"),
        ("PRINTER_STATUS_PAPER_OUT", "Sin papel"),
        ("PRINTER_STATUS_PAPER_JAM", "Atasco"),
        ("PRINTER_STATUS_BUSY", "Ocupada"),
    ]
    return {getattr(win32print, a): l for a, l in pairs if hasattr(win32print, a)}


def _job_status_flags() -> dict[int, str]:
    pairs = [
        ("JOB_STATUS_PAUSED", "Pausado"),
        ("JOB_STATUS_PRINTING", "Imprimiendo"),
        ("JOB_STATUS_SPOOLING", "En cola"),
        ("JOB_STATUS_ERROR", "Error"),
    ]
    return {getattr(win32print, a): l for a, l in pairs if hasattr(win32print, a)}


STATUS_FLAGS = _printer_status_flags()
JOB_STATUS_FLAGS = _job_status_flags()


def _decode_status(status: int, flag_map: dict[int, str]) -> str:
    if status == 0:
        return "Disponible"
    parts = [label for flag, label in flag_map.items() if status & flag]
    return ", ".join(parts) if parts else "Estado desconocido"


def _connection_type(attributes: int) -> str:
    if attributes & win32print.PRINTER_ATTRIBUTE_NETWORK:
        return "Red"
    if attributes & win32print.PRINTER_ATTRIBUTE_LOCAL:
        return "Local"
    return "—"


def list_printers() -> list[PrinterInfo]:
    default_name = get_default_printer()
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    raw = win32print.EnumPrinters(flags, None, 2)
    result: list[PrinterInfo] = []
    for entry in raw:
        name = entry.get("pPrinterName", "")
        result.append(
            PrinterInfo(
                name=name,
                status=_decode_status(entry.get("Status", 0), STATUS_FLAGS),
                driver=entry.get("pDriverName") or "—",
                port=entry.get("pPortName") or "—",
                location=entry.get("pLocation") or "—",
                comment=entry.get("pComment") or "—",
                is_default=name == default_name,
                connection=_connection_type(entry.get("Attributes", 0)),
            )
        )
    return result


def get_default_printer() -> str | None:
    try:
        return win32print.GetDefaultPrinter()
    except win32print.error as e:
        logger.error("GetDefaultPrinter: %s", e)
        return None


def set_default_printer(name: str) -> None:
    win32print.SetDefaultPrinter(name)


def get_printer_status(name: str) -> str:
    handle = win32print.OpenPrinter(name)
    try:
        info = win32print.GetPrinter(handle, 2)
        return _decode_status(info.get("Status", 0), STATUS_FLAGS)
    finally:
        win32print.ClosePrinter(handle)


def list_print_jobs(printer_name: str) -> list[PrintJobInfo]:
    handle = win32print.OpenPrinter(printer_name)
    try:
        jobs = win32print.EnumJobs(handle, 0, -1, 2)
        out: list[PrintJobInfo] = []
        for job in jobs:
            submitted = job.get("Submitted")
            if submitted:
                try:
                    dt_str = submitted.strftime("%Y-%m-%d %H:%M:%S")
                except AttributeError:
                    dt_str = str(submitted)
            else:
                dt_str = "—"
            out.append(
                PrintJobInfo(
                    job_id=job.get("JobId", 0),
                    document=job.get("pDocument") or "—",
                    user=job.get("pUserName") or "—",
                    status=_decode_status(job.get("Status", 0), JOB_STATUS_FLAGS),
                    size=job.get("Size"),
                    pages=job.get("TotalPages") if job.get("TotalPages") else None,
                    submitted=dt_str,
                )
            )
        return out
    finally:
        win32print.ClosePrinter(handle)


def _set_job_command(printer_name: str, job_id: int, command: int) -> None:
    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.SetJob(handle, job_id, 0, None, command)
    finally:
        win32print.ClosePrinter(handle)


def cancel_job(printer_name: str, job_id: int) -> None:
    _set_job_command(printer_name, job_id, win32print.JOB_CONTROL_DELETE)


def pause_job(printer_name: str, job_id: int) -> None:
    _set_job_command(printer_name, job_id, win32print.JOB_CONTROL_PAUSE)


def resume_job(printer_name: str, job_id: int) -> None:
    _set_job_command(printer_name, job_id, win32print.JOB_CONTROL_RESUME)
