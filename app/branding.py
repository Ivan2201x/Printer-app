"""Logo e icono de la aplicación."""

from pathlib import Path

import customtkinter as ctk
from PIL import Image


def app_icon_path(base_dir: Path) -> Path:
    return base_dir / "assets" / "icon.ico"


def app_logo_path(base_dir: Path) -> Path:
    return base_dir / "assets" / "logo.png"


def load_header_logo(base_dir: Path, size: int = 44) -> ctk.CTkImage | None:
    path = app_logo_path(base_dir)
    if not path.is_file():
        return None
    try:
        img = Image.open(path)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    except OSError:
        return None
