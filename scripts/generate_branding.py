"""Genera icon.ico y logo.png (impresora) en assets/."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ACCENT = "#0078D4"
PAPER = "#F3F4F6"
BODY = "#1E1E1E"


def draw_printer(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = size // 8
    # Cuerpo
    x0, y0 = m, size // 3
    x1, y1 = size - m, size - m
    d.rounded_rectangle([x0, y0, x1, y1], radius=size // 16, fill=ACCENT)
    # Bandeja superior
    d.rounded_rectangle(
        [x0 + m // 2, y0 - size // 6, x1 - m // 2, y0 + m],
        radius=size // 24,
        fill=BODY,
    )
    # Papel saliendo
    px0, py0 = size // 3, m
    px1, py1 = 2 * size // 3, y0 - size // 12
    d.rounded_rectangle([px0, py0, px1, py1], radius=size // 32, fill=PAPER, outline="#CBD5E1")
    # LED
    d.ellipse([x1 - 2 * m, y0 + m, x1 - m, y0 + 2 * m], fill="#4ADE80")
    return img


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    master = draw_printer(256)
    master.save(ASSETS / "logo.png", "PNG")
    master.save(
        ASSETS / "icon.ico",
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"OK: {ASSETS / 'logo.png'}, {ASSETS / 'icon.ico'}")


if __name__ == "__main__":
    main()
