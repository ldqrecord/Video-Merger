# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


datas = collect_data_files("imageio_ffmpeg")
binaries = collect_dynamic_libs("imageio_ffmpeg")

hiddenimports = [
    "moviepy.config",
    "moviepy.editor",
    "proglog",
]

excludes = [
    "av",
    "cv2",
    "matplotlib",
    "numba",
    "pandas",
    "pyarrow",
    "scipy",
    "skimage",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Video_Stitcher_1.0.2_onedir",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Video_Stitcher_1.0.2_onedir",
)
