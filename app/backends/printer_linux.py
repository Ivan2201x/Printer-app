"""Impresoras y cola — Linux (CUPS)."""

import logging
import re

from app.backends.subprocess_util import CommandError, run
from app.printer_models import PrintJobInfo, PrinterInfo

logger = logging.getLogger(__name__)

_PRINTER_RE = re.compile(
    r"^printer\s+(\S+)\s+(?P<rest>.+)$", re.IGNORECASE
)
_JOB_RE = re.compile(
    r"^(?P<printer>[\w\-]+)-(?P<job_id>\d+)\s+(?P<user>\S+)\s+(?P<size>\d+)\s+(?P<date>.+)$"
)


def _lpstat(*args: str):
    return run(["lpstat", *args], timeout=30)


def list_printers() -> list[PrinterInfo]:
    default_name = get_default_printer()
    try:
        cp = _lpstat("-p")
    except CommandError:
        return []
    result: list[PrinterInfo] = []
    for line in cp.stdout.splitlines():
        m = _PRINTER_RE.match(line.strip())
        if not m:
            continue
        name = m.group(1)
        rest = m.group("rest").lower()
        if "disabled" in rest or "paused" in rest:
            status = "Pausada"
        elif "printing" in rest:
            status = "Imprimiendo"
        elif "idle" in rest:
            status = "Disponible"
        else:
            status = rest.split(".")[0].strip() or "—"
        result.append(
            PrinterInfo(
                name=name,
                status=status,
                driver="CUPS",
                port="—",
                location="—",
                comment="—",
                is_default=name == default_name,
                connection="Local/Red",
            )
        )
    return result


def get_default_printer() -> str | None:
    try:
        cp = _lpstat("-d")
    except CommandError:
        return None
    for line in cp.stdout.splitlines():
        if "default destination:" in line.lower():
            return line.split(":", 1)[1].strip().rstrip(".")
    return None


def set_default_printer(name: str) -> None:
    cp = run(["lpoptions", "-d", name], timeout=15)
    if cp.returncode != 0:
        err = (cp.stderr or cp.stdout or "").strip()
        logger.error("lpoptions -d: %s", err)
        raise CommandError("No fue posible establecer la impresora predeterminada.")


def get_printer_status(name: str) -> str:
    cp = _lpstat("-p", name)
    if cp.returncode != 0:
        return "Desconocido"
    line = cp.stdout.strip().lower()
    if "printing" in line:
        return "Imprimiendo"
    if "idle" in line:
        return "Disponible"
    if "disabled" in line:
        return "Deshabilitada"
    return "—"


def list_print_jobs(printer_name: str) -> list[PrintJobInfo]:
    try:
        cp = run(["lpstat", "-o", printer_name], timeout=30)
    except CommandError as e:
        raise CommandError("No fue posible acceder a la cola.") from e
    out: list[PrintJobInfo] = []
    for line in cp.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _JOB_RE.match(line)
        if not m:
            continue
        out.append(
            PrintJobInfo(
                job_id=int(m.group("job_id")),
                document="—",
                user=m.group("user"),
                status="En cola",
                size=int(m.group("size")),
                pages=None,
                submitted=m.group("date").strip(),
            )
        )
    return out


def _job_uri(printer_name: str, job_id: int) -> str:
    return f"{printer_name}-{job_id}"


def cancel_job(printer_name: str, job_id: int) -> None:
    cp = run(["cancel", _job_uri(printer_name, job_id)], timeout=30)
    if cp.returncode != 0:
        raise CommandError("No fue posible cancelar el trabajo.")


def pause_job(printer_name: str, job_id: int) -> None:
    cp = run(["lp", "-i", _job_uri(printer_name, job_id), "-H", "hold"], timeout=30)
    if cp.returncode != 0:
        raise CommandError("No fue posible pausar el trabajo.")


def resume_job(printer_name: str, job_id: int) -> None:
    cp = run(["lp", "-i", _job_uri(printer_name, job_id), "-H", "resume"], timeout=30)
    if cp.returncode != 0:
        raise CommandError("No fue posible reanudar el trabajo.")
