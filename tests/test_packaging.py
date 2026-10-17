import re
from pathlib import Path

import pcc

ROOT = Path(__file__).resolve().parent.parent


def test_spec_excludes_heavy_modules():
    s = (ROOT / "packaging/pcc.spec").read_text()
    for m in ("QtWebEngineCore", "QtWebEngineWidgets", "QtQml", "QtQuick", "QtMultimedia",
              "QtPdf", "QtCharts", "tkinter", "fastapi", "uvicorn", "pydantic"):
        assert f'"{m}"' in s or f'"PySide6.{m}"' in s
    assert "upx=False" in s
    assert "console=False" in s
    assert "openpyxl" in s
    assert "QtSvg" not in s.split("excludes")[1].split("]")[0]


def test_desktop_file():
    d = (ROOT / "packaging/pcc.desktop").read_text()
    for line in ("Name=Print Cost Calculator", "Exec=PrintCostCalculator",
                 "Icon=print-cost-calculator", "Categories=Utility;Office;"):
        assert line in d


def test_scripts_and_docker_present():
    assert "set -euo pipefail" in (ROOT / "packaging/build_linux.sh").read_text()
    assert "Compress-Archive" in (ROOT / "packaging/build_windows.ps1").read_text()
    assert (ROOT / "packaging/AppRun").read_text().startswith("#!/usr/bin/env bash")
    df = (ROOT / "Dockerfile").read_text()
    assert "python:3.12-slim" in df and "EXPOSE 8765" in df and "PCC_CONFIG_DIR=/data" in df
    assert ".venv" in (ROOT / ".dockerignore").read_text()


def test_version_is_readable():
    assert re.search(r'__version__\s*=\s*"[^"]+"', (ROOT / "pcc/__init__.py").read_text())
    assert pcc.__version__


def test_selftest_runs_unfrozen(qapp, capsys, monkeypatch):
    from pcc.gui import app

    monkeypatch.setenv("PCC_SELFTEST", "1")
    assert app.main([]) == 0
    assert "selftest ok" in capsys.readouterr().out
