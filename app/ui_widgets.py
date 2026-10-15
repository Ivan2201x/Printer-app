"""Componentes visuales CustomTkinter + Treeview oscuro."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

import customtkinter as ctk

# Paleta sobria — acento tipo Windows 11
COLORS = {
    "accent": "#0078D4",
    "accent_hover": "#106EBE",
    "card": "#252526",
    "card_border": "#3f3f46",
    "muted": "#9ca3af",
    "tree_bg": "#1e1e1e",
    "tree_fg": "#e5e5e5",
    "tree_head": "#2d2d30",
    "canvas_bg": "#141414",
    "list_bg": "#1e1e1e",
    "list_fg": "#f3f4f6",
}


def init_customtkinter() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")


def setup_dark_treeview_style() -> None:
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "Dark.Treeview",
        background=COLORS["tree_bg"],
        foreground=COLORS["tree_fg"],
        fieldbackground=COLORS["tree_bg"],
        borderwidth=0,
        rowheight=28,
        font=("Segoe UI", 10),
    )
    style.configure(
        "Dark.Treeview.Heading",
        background=COLORS["tree_head"],
        foreground=COLORS["tree_fg"],
        relief="flat",
        font=("Segoe UI", 10, "bold"),
    )
    style.map(
        "Dark.Treeview",
        background=[("selected", COLORS["accent"])],
        foreground=[("selected", "#ffffff")],
    )


def btn_state(widget: Any, enabled: bool) -> None:
    widget.configure(state="normal" if enabled else "disabled")


def create_card(parent: ctk.CTkBaseClass, title: str) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
    card = ctk.CTkFrame(parent, corner_radius=12, fg_color=COLORS["card"], border_width=1, border_color=COLORS["card_border"])
    ctk.CTkLabel(
        card,
        text=title,
        font=ctk.CTkFont(size=14, weight="bold"),
        anchor="w",
    ).pack(fill="x", padx=16, pady=(14, 6))
    body = ctk.CTkFrame(card, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=16, pady=(0, 14))
    return card, body


def create_tree_table(
    parent: ctk.CTkBaseClass,
    columns: tuple[str, ...],
    headings: dict[str, str],
    widths: dict[str, int] | None = None,
    height: int = 8,
) -> tuple[ttk.Treeview, ctk.CTkFrame]:
    host = ctk.CTkFrame(parent, fg_color="transparent")
    host.grid_columnconfigure(0, weight=1)
    host.grid_rowconfigure(0, weight=1)
    inner = tk.Frame(host, bg=COLORS["tree_bg"])
    inner.grid(row=0, column=0, sticky="nsew")
    inner.grid_columnconfigure(0, weight=1)
    inner.grid_rowconfigure(0, weight=1)

    tree = ttk.Treeview(inner, columns=columns, show="headings", height=height, style="Dark.Treeview")
    for col in columns:
        tree.heading(col, text=headings[col])
        w = (widths or {}).get(col, 100)
        tree.column(col, width=w, stretch=True, anchor="w")
    tree.grid(row=0, column=0, sticky="nsew")
    sb = ttk.Scrollbar(inner, orient=tk.VERTICAL, command=tree.yview)
    sb.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=sb.set)
    return tree, host


def accent_button(parent, text: str, command, **kwargs) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent,
        text=text,
        command=command,
        height=38,
        font=ctk.CTkFont(size=13, weight="bold"),
        fg_color=COLORS["accent"],
        hover_color=COLORS["accent_hover"],
        **kwargs,
    )


def hint_label(parent, text: str, **kwargs) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent,
        text=text,
        font=ctk.CTkFont(size=11),
        text_color=COLORS["muted"],
        anchor="w",
        justify="left",
        **kwargs,
    )
