# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


block_cipher = None
app_version = os.environ.get("APP_VERSION", "1.0.2")
app_name = f"Video_Stitcher_{app_version}"


datas = []
datas += collect_data_files("imageio_ffmpeg")

binaries = []
binaries += collect_dynamic_libs("imageio_ffmpeg")

hiddenimports = []
hiddenimports += [
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
    exclude_binaries=False,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
