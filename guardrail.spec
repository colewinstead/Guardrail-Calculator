# PyInstaller spec for Guardrail calculator with embedded manual PDF
# Build with: pyinstaller guardrail.spec -y

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

app_script = "guardrail_V8.5.py"

a = Analysis(
    [app_script],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=[
        ("gr manual.pdf", "."),
        ("GR-4.pdf", "."),
        ("GR-4a.pdf", "."),
    ],
    hiddenimports=collect_submodules("pypdf"),
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
    name="guardrail",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI app (Tkinter); set True if you prefer a console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
