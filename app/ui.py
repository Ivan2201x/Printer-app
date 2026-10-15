"""Interfaz CustomTkinter (lógica de negocio sin cambios)."""

import logging
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk

from app import config_service
from app.branding import load_header_logo
from app.platform import com_thread, is_windows, platform_label
from app.ui_widgets import (
    COLORS,
    accent_button,
    btn_state,
    create_card,
    create_tree_table,
    hint_label,
    init_customtkinter,
    setup_dark_treeview_style,
)
from app.pdf_service import (
    cleanup_paths,
    images_to_pdf,
    save_single_image_as_format,
)
from app.print_service import PrintError, print_file
from app.printer_service import (
    PrinterInfo,
    cancel_job,
    get_default_printer,
    list_print_jobs,
    list_printers,
    pause_job,
    resume_job,
    set_default_printer,
)
from app.scanner_service import ScannerError, list_scanners, scan_to_temp_file
from app.utils import (
    COLOR_MODES,
    DPI_OPTIONS,
    OUTPUT_FORMATS,
    default_scan_name,
    expand_user_path,
    file_type_label,
    format_bytes,
    project_root,
    safe_filename,
    unique_path,
)

logger = logging.getLogger(__name__)


class MainApp:
    def __init__(self, root: ctk.CTk, base_dir: Path) -> None:
        self.root = root
        self.base_dir = base_dir
        self.temp_dir = base_dir / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.config = config_service.load_config(base_dir)
        self.printers: list[PrinterInfo] = []
        self.selected_file: Path | None = None
        self.scanners: list = []
        self.scan_pages: list[Path] = []
        self.pending_preview: Path | None = None
        self._preview_photo = None
        self._preview_source: Path | None = None
        self._preview_pil: Image.Image | None = None
        self._preview_scale: float = 1.0
        self._preview_fit_scale_value: float = 1.0

        init_customtkinter()
        setup_dark_treeview_style()
        root.title(f"Gestor de Impresión y Escaneo — {platform_label()}")
        root.geometry("1100x780")
        root.minsize(920, 680)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=1)

        self._scan_backend = "WIA" if is_windows() else "SANE"
        self._build_ui()
        self._load_config_into_ui()
        self.refresh_printers_async()
        self.refresh_scanners_async()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._header_logo = load_header_logo(self.base_dir)
        if self._header_logo:
            ctk.CTkLabel(header, text="", image=self._header_logo).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(
            header,
            text="Gestor de Impresión y Escaneo",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            header,
            text=platform_label(),
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
        ).pack(side="left", padx=(12, 0))

        self.tabview = ctk.CTkTabview(main, corner_radius=10)
        self.tabview.grid(row=1, column=0, sticky="nsew")
        self.tabview.add("Impresión")
        self.tabview.add("Escáner")
        self.tabview.add("Configuración")

        self._build_print_tab(self.tabview.tab("Impresión"))
        self._build_scan_tab(self.tabview.tab("Escáner"))
        self._build_settings_tab(self.tabview.tab("Configuración"))

        self.status_var = tk.StringVar(value="Listo")
        self.status_label = ctk.CTkLabel(
            main,
            textvariable=self.status_var,
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"],
        )
        self.status_label.grid(row=2, column=0, sticky="ew", pady=(10, 0))

    def _run_bg(self, work, on_done=None, busy_msg="Procesando...", on_always=None) -> None:
        self.status_var.set(busy_msg)

        def runner():
            with com_thread():
                try:
                    result = work()
                except Exception as e:
                    result = e

            def finish():
                try:
                    if isinstance(result, Exception):
                        logger.error("Tarea en segundo plano: %s", result, exc_info=result)
                        messagebox.showerror("Error", str(result) or "Operación fallida.")
                    elif on_done:
                        on_done(result)
                finally:
                    if on_always:
                        on_always()
                    self.status_var.set("Listo")

            self.root.after(0, finish)

        threading.Thread(target=runner, daemon=True).start()

    # ——— Impresión ———

    def _on_print_printer_changed(self, _choice: str = "") -> None:
        self.refresh_queue_async()

    def _build_print_tab(self, tab: ctk.CTkFrame) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        top_card, top = create_card(tab, "Impresoras instaladas")
        top_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(4, 10))
        top.grid_columnconfigure(0, weight=1)

        cols = ("name", "status", "driver", "port", "location", "default", "connection")
        headings = {
            "name": "Nombre",
            "status": "Estado",
            "driver": "Driver",
            "port": "Puerto",
            "location": "Ubicación",
            "default": "Predeterminada",
            "connection": "Tipo",
        }
        self.printer_tree, tree_host = create_tree_table(
            top, cols, headings, widths={"name": 180}, height=5
        )
        tree_host.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        top.grid_rowconfigure(0, weight=1)

        btn_row = ctk.CTkFrame(top, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew")
        self.btn_refresh_printers = ctk.CTkButton(
            btn_row, text="Actualizar impresoras", command=self.refresh_printers_async
        )
        self.btn_refresh_printers.pack(side="left", padx=(0, 8))
        self.btn_set_default = ctk.CTkButton(
            btn_row, text="Establecer como predeterminada", command=self._set_default_printer
        )
        self.btn_set_default.pack(side="left")

        self.default_printer_var = tk.StringVar(value="—")
        def_row = ctk.CTkFrame(top, fg_color="transparent")
        def_row.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ctk.CTkLabel(def_row, text="Predeterminada:", text_color=COLORS["muted"]).pack(side="left")
        ctk.CTkLabel(def_row, textvariable=self.default_printer_var, font=ctk.CTkFont(weight="bold")).pack(
            side="left", padx=(8, 0)
        )

        left_card, left = create_card(tab, "Imprimir documento")
        left_card.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        left.grid_columnconfigure(1, weight=1)

        hint_label(
            left,
            text="1. Impresora  →  2. Archivo  →  3. Copias  →  4. Enviar",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        ctk.CTkLabel(left, text="Impresora").grid(row=1, column=0, sticky="w", pady=4)
        self.print_printer_combo = ctk.CTkComboBox(
            left, values=[], state="readonly", command=self._on_print_printer_changed
        )
        self.print_printer_combo.grid(row=1, column=1, sticky="ew", pady=4, padx=(8, 0))

        ctk.CTkLabel(left, text="Copias").grid(row=2, column=0, sticky="w", pady=4)
        self.copies_var = tk.StringVar(value="1")
        ctk.CTkEntry(left, textvariable=self.copies_var, width=80).grid(
            row=2, column=1, sticky="w", pady=4, padx=(8, 0)
        )

        self.btn_select_file = ctk.CTkButton(left, text="Seleccionar archivo…", command=self._select_print_file)
        self.btn_select_file.grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 4))

        self.file_name_var = tk.StringVar(value="Ningún archivo seleccionado")
        self.file_path_var = tk.StringVar(value="")
        self.file_type_var = tk.StringVar(value="—")
        ctk.CTkLabel(left, text="Archivo", anchor="nw").grid(row=4, column=0, sticky="nw", pady=4)
        info = ctk.CTkFrame(left, fg_color="transparent")
        info.grid(row=4, column=1, sticky="ew", padx=(8, 0))
        ctk.CTkLabel(info, textvariable=self.file_name_var, anchor="w", wraplength=340).pack(anchor="w")
        ctk.CTkLabel(
            info, textvariable=self.file_path_var, anchor="w", wraplength=340, text_color=COLORS["muted"]
        ).pack(anchor="w")
        row_t = ctk.CTkFrame(info, fg_color="transparent")
        row_t.pack(anchor="w")
        ctk.CTkLabel(row_t, text="Tipo:", text_color=COLORS["muted"]).pack(side="left")
        ctk.CTkLabel(row_t, textvariable=self.file_type_var).pack(side="left", padx=(4, 0))

        self.btn_print = accent_button(left, "Enviar a imprimir", self._do_print)
        self.btn_print.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(16, 0))

        right_card, right = create_card(tab, "Cola de impresión")
        right_card.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=(6, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)

        qcols = ("id", "document", "user", "status", "size", "pages", "submitted")
        qh = {
            "id": "ID",
            "document": "Documento",
            "user": "Usuario",
            "status": "Estado",
            "size": "Tamaño",
            "pages": "Páginas",
            "submitted": "Fecha/hora",
        }
        self.queue_tree, q_host = create_tree_table(right, qcols, qh, height=14)
        q_host.grid(row=0, column=0, sticky="nsew")

        qbtn = ctk.CTkFrame(right, fg_color="transparent")
        qbtn.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.btn_refresh_queue = ctk.CTkButton(qbtn, text="Actualizar cola", command=self.refresh_queue_async)
        self.btn_refresh_queue.pack(side="left", padx=(0, 6))
        ctk.CTkButton(qbtn, text="Cancelar", width=90, command=self._cancel_job).pack(side="left", padx=4)
        ctk.CTkButton(qbtn, text="Pausar", width=80, command=lambda: self._job_control("pause")).pack(
            side="left", padx=4
        )
        ctk.CTkButton(qbtn, text="Reanudar", width=90, command=lambda: self._job_control("resume")).pack(
            side="left", padx=4
        )

    def refresh_printers_async(self) -> None:
        btn_state(self.btn_refresh_printers, False)

        def work():
            return list_printers()

        def done(printers):
            self.printers = printers
            self._fill_printer_tree()
            names = [p.name for p in printers]
            self.print_printer_combo.configure(values=names or [""])
            default = get_default_printer()
            self.default_printer_var.set(default or "—")
            if default and default in names:
                self.print_printer_combo.set(default)
            elif names:
                self.print_printer_combo.set(names[0])
            if not names:
                messagebox.showwarning("Impresoras", "No se encontraron impresoras instaladas.")
            self.refresh_queue_async()

        self._run_bg(
            work,
            on_done=done,
            busy_msg="Consultando dispositivos...",
            on_always=lambda: btn_state(self.btn_refresh_printers, True),
        )

    def _fill_printer_tree(self) -> None:
        for i in self.printer_tree.get_children():
            self.printer_tree.delete(i)
        for p in self.printers:
            self.printer_tree.insert(
                "",
                tk.END,
                iid=p.name,
                values=(
                    p.name,
                    p.status,
                    p.driver,
                    p.port,
                    p.location,
                    "Sí" if p.is_default else "No",
                    p.connection,
                ),
            )

    def _selected_printer_name(self) -> str | None:
        name = self.print_printer_combo.get().strip()
        if name:
            return name
        sel = self.printer_tree.selection()
        if sel:
            return sel[0]
        return None

    def _set_default_printer(self) -> None:
        name = self._selected_printer_name()
        if not name:
            messagebox.showinfo("Impresora", "Seleccione una impresora.")
            return
        if not messagebox.askyesno("Confirmar", f"¿Establecer «{name}» como impresora predeterminada?"):
            return
        btn_state(self.btn_set_default, False)

        def work():
            set_default_printer(name)

        def done(_):
            self.default_printer_var.set(name)
            self.refresh_printers_async()
            btn_state(self.btn_set_default, True)

        self._run_bg(work, on_done=done, busy_msg="Actualizando predeterminada...")

    def _select_print_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar archivo",
            filetypes=[
                ("Documentos", "*.pdf *.txt *.png *.jpg *.jpeg"),
                ("PDF", "*.pdf"),
                ("Imágenes", "*.png *.jpg *.jpeg"),
                ("Texto", "*.txt"),
                ("Todos", "*.*"),
            ],
        )
        if not path:
            return
        p = Path(path)
        self.selected_file = p
        self.file_name_var.set(p.name)
        self.file_path_var.set(str(p))
        self.file_type_var.set(file_type_label(p))

    def _do_print(self) -> None:
        printer = self._selected_printer_name()
        if not printer:
            messagebox.showinfo("Imprimir", "Seleccione una impresora.")
            return
        if not self.selected_file:
            messagebox.showinfo("Imprimir", "Seleccione un archivo.")
            return
        try:
            copies = int(self.copies_var.get())
        except ValueError:
            copies = 1
        path = self.selected_file
        btn_state(self.btn_print, False)

        def work():
            print_file(path, printer, copies)

        def done(_):
            messagebox.showinfo("Impresión", "Documento enviado a la impresora.")
            self.refresh_queue_async()
            btn_state(self.btn_print, True)

        self._run_bg(
            work,
            on_done=done,
            busy_msg="Enviando a impresora...",
        )

    def refresh_queue_async(self) -> None:
        printer = self._selected_printer_name()
        if not printer:
            return
        btn_state(self.btn_refresh_queue, False)

        def work():
            try:
                return list_print_jobs(printer)
            except Exception as e:
                logger.error("Cola: %s", e)
                raise RuntimeError("No fue posible acceder a la cola.") from e

        def done(jobs):
            for i in self.queue_tree.get_children():
                self.queue_tree.delete(i)
            for j in jobs:
                self.queue_tree.insert(
                    "",
                    tk.END,
                    iid=str(j.job_id),
                    values=(
                        j.job_id,
                        j.document,
                        j.user,
                        j.status,
                        format_bytes(j.size),
                        j.pages if j.pages is not None else "—",
                        j.submitted,
                    ),
                )

        self._run_bg(
            work,
            on_done=done,
            busy_msg="Consultando cola...",
            on_always=lambda: btn_state(self.btn_refresh_queue, True),
        )

    def _queue_selection(self) -> tuple[str, int] | None:
        printer = self._selected_printer_name()
        sel = self.queue_tree.selection()
        if not printer or not sel:
            messagebox.showinfo("Cola", "Seleccione un trabajo en la cola.")
            return None
        return printer, int(sel[0])

    def _cancel_job(self) -> None:
        picked = self._queue_selection()
        if not picked:
            return
        printer, job_id = picked
        if not messagebox.askyesno("Confirmar", f"¿Cancelar el trabajo {job_id}?"):
            return

        def work():
            cancel_job(printer, job_id)

        self._run_bg(work, on_done=lambda _: self.refresh_queue_async(), busy_msg="Cancelando...")

    def _job_control(self, action: str) -> None:
        picked = self._queue_selection()
        if not picked:
            return
        printer, job_id = picked

        def work():
            try:
                if action == "pause":
                    pause_job(printer, job_id)
                else:
                    resume_job(printer, job_id)
            except Exception as e:
                logger.error("Control trabajo: %s", e)
                raise RuntimeError("Windows no permitió esta operación sobre el trabajo.") from e

        self._run_bg(work, on_done=lambda _: self.refresh_queue_async(), busy_msg="Actualizando trabajo...")

    # ——— Escáner ———

    def _build_scan_tab(self, tab: ctk.CTkFrame) -> None:
        tab.grid_columnconfigure(0, weight=3)
        tab.grid_columnconfigure(1, weight=5)
        tab.grid_rowconfigure(2, weight=1)
        tab.grid_rowconfigure(0, weight=0)
        tab.grid_rowconfigure(1, weight=0)

        hint_label(
            tab,
            text="1. Calidad  →  2. Escanear  →  3. Vista previa  →  4. Guardar (PDF multipágina: agregar páginas)",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(4, 10))

        dev_card, dev = create_card(tab, f"Escáneres detectados ({self._scan_backend})")
        dev_card.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        dev.grid_columnconfigure(0, weight=1)
        scols = ("name", "manufacturer", "status")
        self.scanner_tree, scan_tree_host = create_tree_table(
            dev,
            scols,
            {"name": "Nombre", "manufacturer": "Fabricante", "status": "Estado"},
            widths={"name": 220, "manufacturer": 140},
            height=3,
        )
        scan_tree_host.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.btn_refresh_scanners = ctk.CTkButton(dev, text="Buscar escáneres", command=self.refresh_scanners_async)
        self.btn_refresh_scanners.grid(row=1, column=0, sticky="w")

        left_col = ctk.CTkFrame(tab, fg_color="transparent")
        left_col.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        left_col.grid_columnconfigure(0, weight=1)
        left_col.grid_rowconfigure(0, weight=1)

        left_scroll = ctk.CTkScrollableFrame(left_col, fg_color="transparent", label_text="")
        left_scroll.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        cfg_card, cfg = create_card(left_scroll, "Paso 1 — Calidad")
        cfg_card.pack(fill="x", pady=(0, 8))
        cfg.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(cfg, text="Escáner").grid(row=0, column=0, sticky="w", pady=4)
        self.scanner_combo = ctk.CTkComboBox(cfg, values=[], state="readonly")
        self.scanner_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=4)
        ctk.CTkLabel(cfg, text="Resolución").grid(row=1, column=0, sticky="w", pady=4)
        self.dpi_combo = ctk.CTkComboBox(cfg, values=[str(d) for d in DPI_OPTIONS], state="readonly")
        self.dpi_combo.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=4)
        ctk.CTkLabel(cfg, text="Color").grid(row=2, column=0, sticky="w", pady=4)
        self.color_combo = ctk.CTkComboBox(cfg, values=list(COLOR_MODES), state="readonly")
        self.color_combo.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=4)

        act_card, scan_actions = create_card(left_scroll, "Paso 2 — Capturar")
        act_card.pack(fill="x", pady=(0, 8))
        scan_actions.grid_columnconfigure(0, weight=1)
        self.btn_scan = accent_button(scan_actions, "Escanear página", self._scan_acquire_page)
        self.btn_scan.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.btn_add_page = ctk.CTkButton(
            scan_actions, text="Agregar vista al documento", command=self._add_pending_to_document
        )
        self.btn_add_page.grid(row=1, column=0, sticky="ew", pady=4)
        self.btn_discard_pending = ctk.CTkButton(
            scan_actions, text="Descartar vista actual", command=self._discard_pending, fg_color="#4b5563"
        )
        self.btn_discard_pending.grid(row=2, column=0, sticky="ew", pady=4)

        doc_card, doc = create_card(left_scroll, "Paso 3 — Páginas (opcional)")
        doc_card.pack(fill="x", pady=(0, 4))
        doc.grid_columnconfigure(0, weight=1)
        hint_label(doc, text="Un archivo: guarde abajo. Varios: agregue páginas y guarde PDF.").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        list_frame = tk.Frame(doc, bg=COLORS["list_bg"], highlightbackground=COLORS["card_border"], highlightthickness=1)
        list_frame.grid(row=1, column=0, sticky="ew")
        self.pages_list = tk.Listbox(
            list_frame,
            height=4,
            exportselection=False,
            bg=COLORS["list_bg"],
            fg=COLORS["list_fg"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        self.pages_list.pack(fill="x", padx=2, pady=2)
        self.pages_list.bind("<<ListboxSelect>>", self._on_page_list_select)
        mbtn = ctk.CTkFrame(doc, fg_color="transparent")
        mbtn.grid(row=2, column=0, sticky="w", pady=(8, 0))
        ctk.CTkButton(mbtn, text="Quitar", width=70, command=self._remove_page).pack(side="left", padx=(0, 4))
        ctk.CTkButton(mbtn, text="↑", width=36, command=lambda: self._move_page(-1)).pack(side="left", padx=2)
        ctk.CTkButton(mbtn, text="↓", width=36, command=lambda: self._move_page(1)).pack(side="left", padx=2)

        save_card, save_frame = create_card(left_col, "Paso 4 — Guardar en disco")
        save_card.grid(row=1, column=0, sticky="ew")
        save_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(save_frame, text="Formato").grid(row=0, column=0, sticky="w", pady=4)
        self.format_combo = ctk.CTkComboBox(save_frame, values=list(OUTPUT_FORMATS), state="readonly")
        self.format_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=4)
        ctk.CTkLabel(save_frame, text="Carpeta").grid(row=1, column=0, sticky="w", pady=4)
        self.scan_folder_var = tk.StringVar()
        ctk.CTkEntry(save_frame, textvariable=self.scan_folder_var).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=4
        )
        ctk.CTkButton(save_frame, text="Elegir…", width=70, command=self._pick_scan_folder).grid(
            row=1, column=2, padx=(6, 0)
        )
        ctk.CTkLabel(save_frame, text="Nombre").grid(row=2, column=0, sticky="w", pady=4)
        self.scan_name_var = tk.StringVar()
        ctk.CTkEntry(save_frame, textvariable=self.scan_name_var).grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4
        )
        hint_label(save_frame, text="Nombre vacío = generado automáticamente.").grid(row=3, column=0, columnspan=3, sticky="w")
        sbtn = ctk.CTkFrame(save_frame, fg_color="transparent")
        sbtn.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        sbtn.grid_columnconfigure(0, weight=1)
        self.btn_save_scan = accent_button(sbtn, "Guardar documento…", self._save_scan_document)
        self.btn_save_scan.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(sbtn, text="Descartar todo", fg_color="#4b5563", command=self._clear_scan_session).grid(
            row=0, column=1, sticky="ew"
        )

        preview_card, preview = create_card(tab, "Vista previa — confirme antes de guardar")
        preview_card.grid(row=2, column=1, sticky="nsew")
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_rowconfigure(2, weight=1)

        preview_head = ctk.CTkFrame(preview, fg_color="transparent")
        preview_head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        preview_head.grid_columnconfigure(0, weight=1)
        self.preview_hint_var = tk.StringVar(value="Pulse «Escanear página» para ver aquí el resultado.")
        ctk.CTkLabel(preview_head, textvariable=self.preview_hint_var, wraplength=360, justify="left").grid(
            row=0, column=0, sticky="w"
        )
        zoom_bar = ctk.CTkFrame(preview_head, fg_color="transparent")
        zoom_bar.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(zoom_bar, text="−", width=36, command=self._preview_zoom_out).pack(side="left", padx=2)
        self.preview_zoom_var = tk.StringVar(value="—")
        ctk.CTkLabel(zoom_bar, textvariable=self.preview_zoom_var, width=56).pack(side="left", padx=4)
        ctk.CTkButton(zoom_bar, text="+", width=36, command=self._preview_zoom_in).pack(side="left", padx=2)
        ctk.CTkButton(zoom_bar, text="Ajustar", width=72, command=self._preview_zoom_fit).pack(side="left", padx=(6, 0))

        preview_box = ctk.CTkFrame(preview, fg_color=COLORS["canvas_bg"], corner_radius=8)
        preview_box.grid(row=2, column=0, sticky="nsew")
        preview_box.grid_columnconfigure(0, weight=1)
        preview_box.grid_rowconfigure(0, weight=1)
        self.preview_canvas = tk.Canvas(preview_box, highlightthickness=0, bg=COLORS["canvas_bg"])
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        pv_v = ttk.Scrollbar(preview_box, orient=tk.VERTICAL, command=self.preview_canvas.yview)
        pv_v.grid(row=0, column=1, sticky="ns")
        pv_h = ttk.Scrollbar(preview, orient=tk.HORIZONTAL, command=self.preview_canvas.xview)
        pv_h.grid(row=3, column=0, sticky="ew")
        self.preview_canvas.configure(yscrollcommand=pv_v.set, xscrollcommand=pv_h.set)
        self._preview_canvas_image_id = None
        self._bind_preview_scroll()
        hint_label(preview, text="Scroll: rueda. Zoom: Ctrl + rueda o − / +.").grid(row=4, column=0, sticky="w", pady=(8, 0))

        self._clear_preview_display()
        self._update_scan_action_states()

    def refresh_scanners_async(self) -> None:
        btn_state(self.btn_refresh_scanners, False)

        def work():
            return list_scanners()

        def done(scanners):
            self.scanners = scanners
            for i in self.scanner_tree.get_children():
                self.scanner_tree.delete(i)
            ids = []
            for s in scanners:
                self.scanner_tree.insert(
                    "",
                    tk.END,
                    values=(s.name, s.manufacturer, s.status),
                )
                ids.append((s.name, s.device_id))
            names = [n for n, _ in ids]
            self.scanner_combo.configure(values=names or [""])
            self._scanner_id_map = {n: did for n, did in ids}
            if ids:
                self.scanner_combo.set(names[0])
            else:
                messagebox.showwarning(
                    "Escáner",
                    f"No se encontraron escáneres ({self._scan_backend}).",
                )
        self._scanner_id_map = {}
        self._run_bg(
            work,
            on_done=done,
            busy_msg="Consultando escáneres...",
            on_always=lambda: btn_state(self.btn_refresh_scanners, True),
        )

    def _pick_scan_folder(self) -> None:
        folder = filedialog.askdirectory(title="Carpeta de escaneos")
        if folder:
            self.scan_folder_var.set(folder)

    def _scan_device_params(self) -> tuple[str, int, str]:
        name = self.scanner_combo.get()
        device_id = self._scanner_id_map.get(name)
        if not device_id:
            raise ScannerError("Seleccione un escáner.")
        try:
            dpi = int(self.dpi_combo.get())
        except ValueError:
            dpi = 300
        color = self.color_combo.get() or "Color"
        return device_id, dpi, color

    def _update_scan_action_states(self) -> None:
        has_pending = self.pending_preview is not None and self.pending_preview.is_file()
        has_doc = len(self.scan_pages) > 0
        btn_state(self.btn_add_page, has_pending)
        btn_state(self.btn_discard_pending, has_pending)
        btn_state(self.btn_save_scan, has_pending or has_doc)

    def _pages_for_save(self) -> list[Path]:
        pages = list(self.scan_pages)
        if self.pending_preview and self.pending_preview.is_file():
            if self.pending_preview not in pages:
                pages.append(self.pending_preview)
        return pages

    def _release_orphan_pending(self) -> None:
        if (
            self.pending_preview
            and self.pending_preview.is_file()
            and self.pending_preview not in self.scan_pages
        ):
            try:
                self.pending_preview.unlink(missing_ok=True)
            except OSError:
                pass
        self.pending_preview = None

    def _scan_acquire_page(self) -> None:
        if self.pending_preview and self.pending_preview not in self.scan_pages:
            if not messagebox.askyesno(
                "Nueva captura",
                "Hay una vista previa sin guardar.\n¿Descartarla y escanear de nuevo?",
            ):
                return
            self._release_orphan_pending()

        btn_state(self.btn_scan, False)

        def work():
            device_id, dpi, color = self._scan_device_params()
            tmp = scan_to_temp_file(device_id, dpi, color)
            dest = self.temp_dir / f"preview_{tmp.name}"
            dest.write_bytes(tmp.read_bytes())
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            return dest

        def done(path: Path):
            self.pending_preview = path
            self._show_preview(path)
            self.preview_hint_var.set(
                "Revise la imagen. Guarde en disco o agregue al documento para más páginas."
            )
            self._update_scan_action_states()
            btn_state(self.btn_scan, True)

        def on_err(e):
            if isinstance(e, ScannerError):
                messagebox.showerror("Escaneo", str(e))
            else:
                messagebox.showerror("Escaneo", str(e) or "No fue posible escanear.")
            btn_state(self.btn_scan, True)

        self._run_bg_with_err(work, on_done=done, on_err=on_err, busy_msg="Escaneando…")

    def _run_bg_with_err(self, work, on_done, on_err, busy_msg="Procesando...") -> None:
        self.status_var.set(busy_msg)

        def runner():
            err = None
            result = None
            with com_thread():
                try:
                    result = work()
                except Exception as e:
                    err = e

            def finish():
                if err:
                    on_err(err)
                else:
                    on_done(result)
                self.status_var.set("Listo")

            self.root.after(0, finish)

        threading.Thread(target=runner, daemon=True).start()

    def _add_pending_to_document(self) -> None:
        if not self.pending_preview or not self.pending_preview.is_file():
            messagebox.showinfo("Documento", "Primero escanee una página.")
            return
        if self.pending_preview in self.scan_pages:
            messagebox.showinfo("Documento", "Esta página ya está en el documento.")
            return
        self.scan_pages.append(self.pending_preview)
        n = len(self.scan_pages)
        self.pages_list.insert(tk.END, f"Página {n}")
        self.pages_list.selection_clear(0, tk.END)
        self.pages_list.selection_set(tk.END)
        self.pending_preview = None
        self.preview_hint_var.set(
            f"{n} página(s) en el documento. Escanee otra o pulse Guardar documento."
        )
        self._update_scan_action_states()

    def _discard_pending(self) -> None:
        if not self.pending_preview:
            return
        if not messagebox.askyesno("Descartar", "¿Descartar la vista previa actual?"):
            return
        self._release_orphan_pending()
        if self.scan_pages:
            self._show_preview(self.scan_pages[-1])
            self.preview_hint_var.set("Vista previa de la última página del documento.")
        else:
            self._clear_preview_display()
        self._update_scan_action_states()

    def _on_page_list_select(self, _event=None) -> None:
        sel = self.pages_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.scan_pages):
            self._show_preview(self.scan_pages[idx])
            self.preview_hint_var.set(f"Vista previa — página {idx + 1} del documento.")

    def _remove_page(self) -> None:
        sel = self.pages_list.curselection()
        if not sel:
            return
        idx = sel[0]
        path = self.scan_pages.pop(idx)
        self.pages_list.delete(idx)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        self._refresh_page_list_labels()
        self._update_scan_action_states()
        if self.scan_pages:
            self._show_preview(self.scan_pages[min(idx, len(self.scan_pages) - 1)])
        elif self.pending_preview:
            self._show_preview(self.pending_preview)
        else:
            self._clear_preview_display()

    def _refresh_page_list_labels(self) -> None:
        self.pages_list.delete(0, tk.END)
        for i, _p in enumerate(self.scan_pages, start=1):
            self.pages_list.insert(tk.END, f"Página {i}")

    def _move_page(self, delta: int) -> None:
        sel = self.pages_list.curselection()
        if not sel:
            return
        idx = sel[0]
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(self.scan_pages):
            return
        self.scan_pages[idx], self.scan_pages[new_idx] = self.scan_pages[new_idx], self.scan_pages[idx]
        self._refresh_page_list_labels()
        self.pages_list.selection_set(new_idx)
        self._show_preview(self.scan_pages[new_idx])

    def _resolve_save_path(self, fmt: str) -> Path:
        folder = expand_user_path(self.scan_folder_var.get())
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ScannerError("Seleccione una carpeta de destino válida.") from e
        name = self.scan_name_var.get().strip()
        if not name:
            ext = "pdf" if fmt == "PDF" else fmt.lower()
            name = default_scan_name(ext)
        else:
            name = safe_filename(name)
            if "." not in name:
                name += ".pdf" if fmt == "PDF" else f".{fmt.lower()}"
        return unique_path(folder / name)

    def _save_scan_document(self) -> None:
        pages = self._pages_for_save()
        if not pages:
            messagebox.showinfo("Guardar", "Escanee al menos una página antes de guardar.")
            return

        fmt = (self.format_combo.get() or "PDF").upper()
        if len(pages) > 1 and fmt != "PDF":
            messagebox.showinfo(
                "Guardar",
                "Varias páginas solo se pueden guardar como PDF.\n"
                "Cambie el formato a PDF o deje una sola página.",
            )
            return

        try:
            dest = self._resolve_save_path(fmt)
        except ScannerError as e:
            messagebox.showerror("Guardar", str(e))
            return

        btn_state(self.btn_save_scan, False)
        pages_copy = list(pages)

        def work():
            if fmt == "PDF":
                if len(pages_copy) == 1:
                    save_single_image_as_format(pages_copy[0], dest, "PDF")
                else:
                    images_to_pdf(pages_copy, dest)
            else:
                save_single_image_as_format(pages_copy[0], dest, fmt)
            return dest

        def done(saved: Path):
            messagebox.showinfo("Guardar", f"Documento guardado en:\n{saved}")
            self._clear_scan_session(keep_final=True)
            self.preview_hint_var.set("Guardado. Puede escanear un nuevo documento.")
            self._update_scan_action_states()
            btn_state(self.btn_save_scan, True)

        def on_err(e):
            messagebox.showerror("Guardar", str(e) or "No fue posible guardar el documento.")
            btn_state(self.btn_save_scan, True)

        self._run_bg_with_err(work, on_done=done, on_err=on_err, busy_msg="Guardando…")

    def _clear_scan_session(self, keep_final: bool = False) -> None:
        if not keep_final:
            self._release_orphan_pending()
            cleanup_paths(self.scan_pages)
        else:
            to_clean = list(self.scan_pages)
            if self.pending_preview and self.pending_preview not in to_clean:
                to_clean.append(self.pending_preview)
            cleanup_paths(to_clean)
            self.pending_preview = None
        self.scan_pages.clear()
        self.pages_list.delete(0, tk.END)
        self._clear_preview_display()
        self._update_scan_action_states()

    def _bind_preview_scroll(self) -> None:
        def on_wheel(event):
            if event.state & 0x0004:  # Ctrl — zoom
                if event.delta > 0 or getattr(event, "num", 0) == 4:
                    self._preview_zoom_in()
                else:
                    self._preview_zoom_out()
                return "break"
            if event.delta:
                self.preview_canvas.yview_scroll(int(-event.delta / 120), "units")
            return "break"

        def on_wheel_linux(event):
            if event.state & 0x0004:
                self._preview_zoom_in() if event.num == 4 else self._preview_zoom_out()
                return "break"
            self.preview_canvas.yview_scroll(-1 if event.num == 4 else 1, "units")
            return "break"

        def on_shift_wheel(event):
            if event.delta:
                self.preview_canvas.xview_scroll(int(-event.delta / 120), "units")
            return "break"

        w = self.preview_canvas
        w.bind("<Enter>", lambda _e: w.focus_set())
        w.bind("<MouseWheel>", on_wheel)
        w.bind("<Shift-MouseWheel>", on_shift_wheel)
        w.bind("<Control-MouseWheel>", on_wheel)
        w.bind("<Button-4>", on_wheel_linux)
        w.bind("<Button-5>", on_wheel_linux)

    def _preview_fit_scale(self) -> float:
        if not self._preview_pil:
            return 1.0
        self.preview_canvas.update_idletasks()
        cw = max(self.preview_canvas.winfo_width(), 220)
        return max(0.05, (cw - 16) / self._preview_pil.width)

    def _preview_zoom_label(self) -> str:
        if not self._preview_pil or self._preview_fit_scale_value <= 0:
            return "—"
        pct = int(round(100 * self._preview_scale / self._preview_fit_scale_value))
        return f"{pct}%"

    def _render_preview_canvas(self) -> None:
        if not self._preview_pil:
            return
        w = max(1, int(self._preview_pil.width * self._preview_scale))
        h = max(1, int(self._preview_pil.height * self._preview_scale))
        shown = self._preview_pil.resize((w, h), Image.Resampling.LANCZOS)
        self._preview_photo = ImageTk.PhotoImage(shown)
        self.preview_canvas.delete("all")
        self._preview_canvas_image_id = self.preview_canvas.create_image(
            0, 0, anchor=tk.NW, image=self._preview_photo
        )
        self.preview_canvas.configure(scrollregion=(0, 0, w, h))
        self.preview_zoom_var.set(self._preview_zoom_label())

    def _preview_zoom_in(self) -> None:
        if not self._preview_pil:
            return
        max_scale = self._preview_fit_scale_value * 4.0
        self._preview_scale = min(self._preview_scale * 1.25, max_scale)
        self._render_preview_canvas()

    def _preview_zoom_out(self) -> None:
        if not self._preview_pil:
            return
        min_scale = self._preview_fit_scale_value * 0.15
        self._preview_scale = max(self._preview_scale / 1.25, min_scale)
        self._render_preview_canvas()

    def _preview_zoom_fit(self) -> None:
        if not self._preview_pil:
            return
        self._preview_fit_scale_value = self._preview_fit_scale()
        self._preview_scale = self._preview_fit_scale_value
        self._render_preview_canvas()

    def _clear_preview_display(self) -> None:
        self._preview_photo = None
        self._preview_source = None
        self._preview_pil = None
        self._preview_scale = 1.0
        self.preview_zoom_var.set("—")
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(
            200,
            120,
            text="Sin imagen\n\nEscanee una página para ver la vista previa aquí.",
            fill="#9ca3af",
            font=("Segoe UI", 10) if is_windows() else ("Sans", 10),
            anchor=tk.CENTER,
        )
        self.preview_canvas.configure(scrollregion=(0, 0, 400, 240))

    def _show_preview(self, path: Path) -> None:
        try:
            with Image.open(path) as im:
                im = im.convert("RGB") if im.mode not in ("RGB", "L") else im.copy()
                w, h = im.size
                max_side = 2400
                if max(w, h) > max_side:
                    ratio = max_side / max(w, h)
                    im = im.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
                self._preview_pil = im
            self._preview_source = path
            self._preview_fit_scale_value = self._preview_fit_scale()
            self._preview_scale = self._preview_fit_scale_value
            self._render_preview_canvas()
        except Exception as e:
            logger.warning("Vista previa: %s", e)
            self._clear_preview_display()

    # ——— Configuración ———

    def _build_settings_tab(self, tab: ctk.CTkFrame) -> None:
        tab.grid_columnconfigure(0, weight=1)
        card, body = create_card(tab, "Preferencias de escaneo")
        card.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        body.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(body, text="Carpeta predeterminada").grid(row=0, column=0, sticky="w", pady=8)
        self.cfg_folder_var = tk.StringVar()
        ctk.CTkEntry(body, textvariable=self.cfg_folder_var).grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=8)
        ctk.CTkButton(body, text="Examinar", width=90, command=self._cfg_pick_folder).grid(row=0, column=2, padx=(8, 0))

        ctk.CTkLabel(body, text="DPI predeterminado").grid(row=1, column=0, sticky="w", pady=8)
        self.cfg_dpi_combo = ctk.CTkComboBox(body, values=[str(d) for d in DPI_OPTIONS], state="readonly")
        self.cfg_dpi_combo.grid(row=1, column=1, sticky="w", padx=(12, 0), pady=8)

        ctk.CTkLabel(body, text="Formato predeterminado").grid(row=2, column=0, sticky="w", pady=8)
        self.cfg_format_combo = ctk.CTkComboBox(body, values=list(OUTPUT_FORMATS), state="readonly")
        self.cfg_format_combo.grid(row=2, column=1, sticky="w", padx=(12, 0), pady=8)

        ctk.CTkLabel(body, text="Color predeterminado").grid(row=3, column=0, sticky="w", pady=8)
        self.cfg_color_combo = ctk.CTkComboBox(body, values=list(COLOR_MODES), state="readonly")
        self.cfg_color_combo.grid(row=3, column=1, sticky="w", padx=(12, 0), pady=8)

        btn = ctk.CTkFrame(body, fg_color="transparent")
        btn.grid(row=4, column=0, columnspan=3, sticky="w", pady=(20, 0))
        accent_button(btn, "Guardar configuración", self._save_settings).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn, text="Restaurar predeterminados", fg_color="#4b5563", command=self._reset_settings).pack(
            side="left"
        )

    def _load_config_into_ui(self) -> None:
        c = self.config
        folder = c.get("scan_folder") or str(Path.home() / "Documents" / "Escaneos")
        self.cfg_folder_var.set(c.get("scan_folder", ""))
        self.scan_folder_var.set(folder)
        dpi = str(c.get("scan_dpi", 300))
        self.cfg_dpi_combo.set(dpi)
        self.dpi_combo.set(dpi)
        fmt = c.get("scan_format", "PDF")
        self.cfg_format_combo.set(fmt)
        self.format_combo.set(fmt)
        color = c.get("scan_color", "Color")
        self.cfg_color_combo.set(color)
        self.color_combo.set(color)

    def _cfg_pick_folder(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.cfg_folder_var.set(folder)

    def _save_settings(self) -> None:
        try:
            dpi = int(self.cfg_dpi_combo.get())
        except ValueError:
            dpi = 300
        self.config = {
            "scan_folder": self.cfg_folder_var.get(),
            "scan_dpi": dpi,
            "scan_format": self.cfg_format_combo.get() or "PDF",
            "scan_color": self.cfg_color_combo.get() or "Color",
        }
        try:
            config_service.save_config(self.base_dir, self.config)
        except OSError:
            messagebox.showerror("Configuración", "No fue posible guardar config.json.")
            return
        self._load_config_into_ui()
        messagebox.showinfo("Configuración", "Configuración guardada.")

    def _reset_settings(self) -> None:
        self.config = config_service.reset_config(self.base_dir)
        self._load_config_into_ui()
        messagebox.showinfo("Configuración", "Valores predeterminados restaurados.")

    def _on_close(self) -> None:
        self._clear_scan_session()
        self.root.destroy()


def create_main_window(root: ctk.CTk, base_dir: Path | None = None) -> MainApp:
    base = base_dir or project_root()
    return MainApp(root, base)
