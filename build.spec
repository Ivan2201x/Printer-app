# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller: pyinstaller build.spec"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ctk_datas = collect_data_files("customtkinter")
ctk_hidden = collect_submodules("customtkinter")
app_datas = [("assets", "assets")] if os.path.isdir("assets") else []

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=ctk_datas + app_datas,
    hiddenimports=[
        *ctk_hidden,
        "win32api",
        "win32print",
        "win32con",
        "win32com",
        "win32com.client",
        "pythoncom",
        "pywintypes",
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="GestorImpresionEscaneo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico" if os.path.isfile("assets/icon.ico") else None,
)
