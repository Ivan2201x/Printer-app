"""Lista escáneres (WIA en Windows, SANE en Linux)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.platform import com_thread, platform_label
from app.scanner_service import list_scanners


def main() -> None:
    print(f"Plataforma: {platform_label()}")
    with com_thread():
        devices = list_scanners()
    if not devices:
        print("No se encontraron escáneres.")
        return
    for d in devices:
        print(f"- {d.name}")
        print(f"    Fabricante: {d.manufacturer}")
        print(f"    ID: {d.device_id}")
        print(f"    Estado: {d.status}")


if __name__ == "__main__":
    main()
