# -*- mode: python ; coding: utf-8 -*-
import sys, os, shutil
path_dir = ['.\\.venv\\Lib\\site-packages','.','app','app\\utils']

a = Analysis(
    ['MainGui.py'],
    pathex=path_dir,
    binaries=[],
    datas=[('tkbidv.png','.')],
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
    [],
    exclude_binaries=True,
    name='MainGui',
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
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MainGui',
)
shutil.copyfile('config.json', '{0}/MainGui/config.json'.format(DISTPATH))
shutil.copyfile('captcha.keras', '{0}/MainGui/captcha.keras'.format(DISTPATH))
shutil.copyfile('template.xlsx', '{0}/MainGui/template.xlsx'.format(DISTPATH))
shutil.copytree('bin', '{0}/MainGui/bin'.format(DISTPATH), dirs_exist_ok=True)  # Fine

