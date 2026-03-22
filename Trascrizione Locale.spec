# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)


project_dir = Path(SPECPATH)
icon_path = project_dir / "assets" / "app_icon.icns"

datas = [
    (str(project_dir / "templates"), "templates"),
    (str(project_dir / "static"), "static"),
    (str(project_dir / "domain_prompt_example.txt"), "."),
]

example_env = project_dir / ".env.local.example"
if example_env.exists():
    datas.append((str(example_env), "."))

binaries = []
hiddenimports = []

for package_name in (
    "faster_whisper",
    "ctranslate2",
    "imageio_ffmpeg",
    "pyannote.audio",
):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package_name)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

datas += collect_data_files("webview")
hiddenimports += collect_submodules("webview.platforms")

for package_name in ("torch", "torchaudio", "soundfile"):
    binaries += collect_dynamic_libs(package_name)

for distribution_name in (
    "Flask",
    "openai",
    "pywebview",
    "faster-whisper",
    "ctranslate2",
    "pyannote.audio",
    "huggingface_hub",
    "imageio-ffmpeg",
):
    try:
        datas += copy_metadata(distribution_name)
    except Exception:
        pass

hiddenimports = sorted(set(hiddenimports + ["webview.platforms.cocoa"]))
datas = sorted(set(datas))
binaries = sorted(set(binaries))

a = Analysis(
    ["desktop_window.py"],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Trascrizione Locale",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Trascrizione Locale",
)

app = BUNDLE(
    coll,
    name="Trascrizione Locale.app",
    icon=str(icon_path) if icon_path.exists() else None,
    bundle_identifier="local.transcription.app",
    info_plist={
        "CFBundleName": "Trascrizione Locale",
        "CFBundleDisplayName": "Trascrizione Locale",
        "CFBundleShortVersionString": "2.0",
        "CFBundleVersion": "2",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    },
)
