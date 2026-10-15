"""Test manual: listar dispositivos WIA (escáneres). Ejecutar desde la raíz del proyecto."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pythoncom

from app.scanner_service import list_scanners


def main() -> None:
    pythoncom.CoInitialize()
    try:
        devices = list_scanners()
        if not devices:
            print("No se encontraron escáneres WIA.")
            return
        for d in devices:
            print(f"- {d.name}")
            print(f"    Fabricante: {d.manufacturer}")
            print(f"    ID: {d.device_id}")
            print(f"    Estado/Puerto: {d.status}")
    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
