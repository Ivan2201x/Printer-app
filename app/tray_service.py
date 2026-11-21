"""Bandeja del sistema: minimizar en segundo plano."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class TrayController:
    def __init__(
        self,
        root,
        base_dir: Path,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self.root = root
        self.base_dir = base_dir
        self.on_show = on_show
        self.on_quit = on_quit
        self._icon = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        try:
            import pystray
            from PIL import Image
        except ImportError:
            logger.warning("pystray no instalado; bandeja desactivada")
            return

        logo = self.base_dir / "assets" / "logo.png"
        if logo.is_file():
            image = Image.open(logo)
        else:
            image = Image.new("RGB", (64, 64), color="#0078D4")

        menu = pystray.Menu(
            pystray.MenuItem("Abrir", lambda _i, _it: self.root.after(0, self._show)),
            pystray.MenuItem("Salir", lambda _i, _it: self.root.after(0, self._quit)),
        )
        self._icon = pystray.Icon("printer_app", image, "Gestor Impresión/Escaneo", menu)
        self._running = True
        self._thread = threading.Thread(target=self._icon.run, daemon=True, name="tray")
        self._thread.start()

    def stop(self) -> None:
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
        self._running = False

    def hide_window(self) -> None:
        self.root.withdraw()

    def _show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.on_show()

    def _quit(self) -> None:
        self.stop()
        self.on_quit()
