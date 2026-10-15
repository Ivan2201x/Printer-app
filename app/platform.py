"""Detección de plataforma y utilidades COM (Windows)."""

import sys
from contextlib import contextmanager
from typing import Iterator


def is_windows() -> bool:
    return sys.platform == "win32"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def platform_label() -> str:
    if is_windows():
        return "Windows"
    if is_linux():
        return "Linux"
    return sys.platform


@contextmanager
def com_thread() -> Iterator[None]:
    """Inicializa COM en hilos secundarios (solo Windows / WIA)."""
    if not is_windows():
        yield
        return
    import pythoncom

    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()
