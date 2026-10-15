"""Creación de PDF multipágina con Pillow."""

import logging
import shutil
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGB", "L"):
        return img.convert("RGB") if img.mode == "L" else img
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    return img.convert("RGB")


def images_to_pdf(image_paths: list[Path], output_pdf: Path) -> None:
    if not image_paths:
        raise ValueError("No hay imágenes para crear el PDF.")
    images: list[Image.Image] = []
    try:
        for p in image_paths:
            im = Image.open(p)
            images.append(_to_rgb(im))
        first, *rest = images
        first.save(
            output_pdf,
            "PDF",
            save_all=True,
            append_images=rest,
            resolution=300.0,
        )
    finally:
        for im in images:
            im.close()


def save_single_image_as_format(
    source: Path, dest: Path, fmt: str
) -> None:
    fmt = fmt.upper()
    with Image.open(source) as im:
        if fmt == "JPG":
            rgb = _to_rgb(im)
            rgb.save(dest, "JPEG", quality=92)
        elif fmt == "PNG":
            im.save(dest, "PNG")
        elif fmt == "PDF":
            _to_rgb(im).save(dest, "PDF", resolution=300.0)
        else:
            raise ValueError(f"Formato no soportado: {fmt}")


def cleanup_paths(paths: list[Path]) -> None:
    for p in paths:
        try:
            if p.is_file():
                p.unlink()
        except OSError as e:
            logger.warning("No se pudo eliminar temporal %s: %s", p, e)


def cleanup_dir_contents(dir_path: Path, pattern: str = "*") -> None:
    if not dir_path.is_dir():
        return
    for f in dir_path.glob(pattern):
        try:
            if f.is_file():
                f.unlink()
        except OSError as e:
            logger.warning("No se pudo eliminar %s: %s", f, e)
