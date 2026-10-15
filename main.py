"""Punto de entrada: logging y loop CustomTkinter."""

import logging
import sys
from pathlib import Path

import customtkinter as ctk

from app.branding import app_icon_path
from app.ui import create_main_window
from app.ui_widgets import init_customtkinter
from app.utils import project_root


def setup_logging(base_dir: Path) -> None:
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def main() -> None:
    base = project_root()
    setup_logging(base)
    init_customtkinter()
    root = ctk.CTk()
    try:
        icon = app_icon_path(base)
        if icon.is_file():
            root.iconbitmap(str(icon))
            root.after(250, lambda: root.iconbitmap(str(icon)))
    except Exception:
        pass
    create_main_window(root, base)
    root.mainloop()


if __name__ == "__main__":
    main()
