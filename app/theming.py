"""Estilo ttk multiplataforma (aspecto más moderno)."""

import sys
import tkinter as tk
from tkinter import ttk


def apply_theme(root: tk.Tk) -> ttk.Style:
    style = ttk.Style(root)
    names = style.theme_names()
    if sys.platform == "win32" and "vista" in names:
        style.theme_use("vista")
    elif "clam" in names:
        style.theme_use("clam")

    if sys.platform == "win32":
        font_ui = ("Segoe UI", 10)
        font_title = ("Segoe UI Semibold", 11)
    else:
        font_ui = ("Cantarell", 10) if sys.platform.startswith("linux") else ("TkDefaultFont", 10)
        font_title = ("Cantarell", 11, "bold")

    style.configure(".", font=font_ui)
    style.configure("TLabel", font=font_ui)
    style.configure("TButton", font=font_ui, padding=(10, 6))
    style.configure("Accent.TButton", font=(font_ui[0], 10, "bold"), padding=(12, 8))
    style.configure("Title.TLabel", font=font_title)
    style.configure("Hint.TLabel", foreground="#505050", font=(font_ui[0], 9))
    style.configure("TLabelframe.Label", font=font_title)
    style.configure("Treeview", rowheight=26, font=font_ui)
    style.configure("Treeview.Heading", font=(font_ui[0], 10, "bold"))
    style.configure("TNotebook.Tab", padding=(12, 6), font=font_ui)

    root.configure(bg=style.lookup("TFrame", "background") or "#f0f0f0")
    return style
