"""Test manual: listar impresoras Windows."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.printer_service import get_default_printer, list_printers


def main() -> None:
    default = get_default_printer()
    print(f"Predeterminada: {default or '—'}")
    printers = list_printers()
    if not printers:
        print("No hay impresoras.")
        return
    for p in printers:
        mark = " *" if p.is_default else ""
        print(f"- {p.name}{mark} [{p.status}] {p.connection}")


if __name__ == "__main__":
    main()
