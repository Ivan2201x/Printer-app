"""Ejecución segura de comandos del sistema (Linux)."""

import logging
import shutil
import subprocess
from subprocess import CompletedProcess

logger = logging.getLogger(__name__)


class CommandError(Exception):
    pass


def require_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise CommandError(
            f"No se encontró «{name}» en el PATH. Instale los paquetes del sistema indicados en el README."
        )
    return path


def run(
    args: list[str],
    *,
    timeout: float = 120,
    input_bytes: bytes | None = None,
) -> CompletedProcess[str]:
    require_command(args[0])
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_bytes,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        logger.error("Timeout: %s", args)
        raise CommandError(f"El comando tardó demasiado: {args[0]}") from e
    except OSError as e:
        logger.error("run %s: %s", args, e)
        raise CommandError(f"No se pudo ejecutar {args[0]}.") from e
