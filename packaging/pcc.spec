# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Print Cost Calculator (one-dir, windowed, no UPX).
# Build from anywhere: python -m PyInstaller --noconfirm --clean packaging/pcc.spec
import re
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821  (SPECPATH injected by PyInstaller)
VERSION = re.search(
    r'__version__\s*=\s*"([^"]+)"', (ROOT / "pcc" / "__init__.py").read_text()
).group(1)

EXCLUDES = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.Qt3DCore",
    "PySide6.QtMultimedia",
    "PySide6.QtPdf",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "tkinter",
    "fastapi",
    "uvicorn",
    "pydantic",
]

a = Analysis(  # noqa: F821
    [str(ROOT / "pcc" / "gui" / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "pcc" / "assets"), "pcc/assets")],
    hiddenimports=["openpyxl", "pcc.core.export_xlsx"],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PrintCostCalculator",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "pcc" / "assets" / "icon.ico"),
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PrintCostCalculator",
)
