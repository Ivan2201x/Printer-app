"""Escaneo SANE — Linux (scanimage)."""

import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

from app.backends.subprocess_util import CommandError, require_command
from app.scanner_models import ScannerDevice, ScannerError

logger = logging.getLogger(__name__)

_DEVICE_RE = re.compile(
    r"^device\s+`([^']+)'\s+is a\s+(.+)$", re.IGNORECASE
)

SANE_COLOR = {
    "Color": "Color",
    "Escala de grises": "Gray",
    "Blanco y negro": "Lineart",
}


def list_scanners() -> list[ScannerDevice]:
    require_command("scanimage")
    try:
        cp = subprocess.run(
            ["scanimage", "-L"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise ScannerError("Tiempo agotado al buscar escáneres.") from e
    except OSError as e:
        raise ScannerError("No fue posible ejecutar scanimage.") from e

    if cp.returncode != 0 and not cp.stdout.strip():
        err = (cp.stderr or "").strip()
        logger.error("scanimage -L: %s", err)
        raise ScannerError(
            "No se encontraron escáneres. Compruebe SANE y permisos (grupo scanner)."
        )

    devices: list[ScannerDevice] = []
    for line in cp.stdout.splitlines():
        m = _DEVICE_RE.match(line.strip())
        if not m:
            continue
        dev_id, desc = m.group(1), m.group(2).strip()
        manufacturer = desc.split()[0] if desc else "—"
        devices.append(
            ScannerDevice(
                device_id=dev_id,
                name=desc or dev_id,
                manufacturer=manufacturer,
                status="SANE",
            )
        )
    return devices


def scan_to_temp_file(
    device_id: str,
    dpi: int,
    color_mode: str,
    use_feeder: bool = False,
) -> Path:
    del use_feeder
    require_command("scanimage")
    mode = SANE_COLOR.get(color_mode, "Color")
    fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="sane_scan_")
    os.close(fd)
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
    out_path = Path(tmp_path)

    args = [
        "scanimage",
        f"--device-name={device_id}",
        f"--resolution={dpi}",
        f"--mode={mode}",
        "--format=png",
    ]
    try:
        cp = subprocess.run(args, capture_output=True, timeout=300, check=False)
    except subprocess.TimeoutExpired as e:
        raise ScannerError("El escaneo tardó demasiado.") from e
    except OSError as e:
        raise ScannerError("No fue posible iniciar el escaneo.") from e

    if cp.returncode != 0 or not cp.stdout:
        err = (cp.stderr or b"").decode(errors="replace").strip().lower()
        logger.error("scanimage: %s", err)
        if "busy" in err or "device busy" in err:
            raise ScannerError("El dispositivo está siendo utilizado por otra aplicación.")
        if "invalid" in err and "resolution" in err:
            raise ScannerError("La resolución seleccionada no es compatible con este escáner.")
        raise ScannerError("No fue posible completar el escaneo.")

    out_path.write_bytes(cp.stdout)
    return out_path
