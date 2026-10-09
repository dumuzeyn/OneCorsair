# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['mp3_ship_gui.py'],
    pathex=[],
    binaries=[
        ('vendor\\yt-dlp\\yt-dlp.exe', 'yt-dlp'),
    ],
    datas=[
        ('assets\\download_icon.ico', 'assets'),
        ('assets\\download_icon.png', 'assets'),
        ('assets\\download_icon.svg', 'assets'),
        ('assets\\window-icons', 'assets/window-icons'),
        ('vendor\\runtime-tools.zip', '.'),
        ('vendor\\yt-dlp\\version.txt', 'yt-dlp'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OneCorsair',
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
    icon=['assets\\download_icon.ico'],
    version='windows_version.txt',
)
