import re
from pathlib import Path

import pytest

import pcc

ROOT = Path(__file__).resolve().parent.parent


def test_spec_excludes_heavy_modules():
    s = (ROOT / "packaging/pcc.spec").read_text(encoding="utf-8")
    for m in ("QtWebEngineCore", "QtWebEngineWidgets", "QtQml", "QtQuick", "QtMultimedia",
              "QtPdf", "QtCharts", "tkinter", "fastapi", "uvicorn", "pydantic"):
        assert f'"{m}"' in s or f'"PySide6.{m}"' in s
    assert "upx=False" in s
    assert "console=False" in s
    assert "openpyxl" in s
    assert "EXCLUDES = [" in s
    assert "QtSvg" not in s.split("EXCLUDES = [")[1].split("]")[0]


def test_desktop_file():
    d = (ROOT / "packaging/pcc.desktop").read_text(encoding="utf-8")
    for line in ("Name=Print Cost Calculator", "Exec=PrintCostCalculator",
                 "Icon=print-cost-calculator", "Categories=Utility;Office;"):
        assert line in d


def test_scripts_and_docker_present():
    assert "set -euo pipefail" in (ROOT / "packaging/build_linux.sh").read_text(encoding="utf-8")
    assert "Compress-Archive" in (ROOT / "packaging/build_windows.ps1").read_text(encoding="utf-8")
    assert (ROOT / "packaging/AppRun").read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
    df = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.12-slim" in df and "EXPOSE 8765" in df and "PCC_CONFIG_DIR=/data" in df
    assert ".venv" in (ROOT / ".dockerignore").read_text(encoding="utf-8")


def test_version_is_readable():
    assert re.search(r'__version__\s*=\s*"[^"]+"', (ROOT / "pcc/__init__.py").read_text(encoding="utf-8"))
    assert pcc.__version__


def test_selftest_runs_unfrozen(qapp, capsys, monkeypatch):
    from pcc.gui import app, invoice_pdf

    rendered = []
    real = invoice_pdf.render_invoice_pdf

    def spy(path, **kw):
        real(path, **kw)
        rendered.append((Path(path).read_bytes()[:4], kw["logo_jpeg"][:2]))
    monkeypatch.setattr(invoice_pdf, "render_invoice_pdf", spy)
    monkeypatch.setenv("PCC_SELFTEST", "1")
    assert app.main([]) == 0
    assert "selftest ok" in capsys.readouterr().out
    assert rendered == [(b"%PDF", b"\xff\xd8")]  # a PDF with a real JPEG logo


@pytest.mark.parametrize("broken", ["jpeg", "pdf"])
def test_selftest_fails_without_image_plugins_or_pdf(qapp, capsys, monkeypatch, broken):
    from pcc.gui import app, invoice_pdf, logo

    if broken == "jpeg":
        monkeypatch.setattr(logo, "load_logo_image",
                            lambda p: (_ for _ in ()).throw(logo.LogoError("no jpeg")))
    else:
        monkeypatch.setattr(invoice_pdf, "render_invoice_pdf", lambda path, **kw: None)
    monkeypatch.setenv("PCC_SELFTEST", "1")
    assert app.main([]) == 1
    assert "selftest FAILED" in capsys.readouterr().err


def test_workflows_present():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    rel = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in ci and "QT_QPA_PLATFORM" in ci
    assert "manylinux_2_28" in rel and "tags:" in rel
    assert "softprops/action-gh-release@v2" in rel


def test_license_and_docs_present():
    assert "MIT License" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "## 0.2.0 \u2014 2026-10-17" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "/openapi.json" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_release_linux_checks_xcb_plugin():
    rel = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    linux = rel.split("\n  linux:")[1].split("\n  python:")[0]
    assert "skip_missing_names_on_install" not in linux
    assert "epel-release" in linux and "powertools" in linux
    assert "xorg-x11-server-Xvfb" in linux
    assert "ldd dist/PrintCostCalculator/_internal/PySide6/Qt/plugins/platforms/libqxcb.so" in linux
    assert 'grep "not found"' in linux and "exit 1" in linux
    assert "xvfb-run -a env QT_QPA_PLATFORM=xcb PCC_EXIT_AFTER_SHOW=1500" in linux
    # every step that relies on pipefail runs under an explicit bash shell
    for step in linux.split("      - ")[1:]:
        if "pipefail" in step or " | " in step:
            assert "shell: bash" in step, step


def test_docker_runs_as_non_root():
    df = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    lines = [ln.strip() for ln in df.splitlines()]
    assert "useradd" in df and "chown" in df and "/data" in df
    user = lines.index("USER pcc")
    assert lines.index(next(ln for ln in lines if ln.startswith("VOLUME"))) > \
        lines.index(next(ln for ln in lines if "chown" in ln))
    assert user > lines.index(next(ln for ln in lines if "useradd" in ln))
    assert user < lines.index(next(ln for ln in lines if ln.startswith("CMD")))


def test_installer_script():
    s = (ROOT / "packaging/installer.iss").read_text(encoding="utf-8")
    for needle in ("8AE3DA70-F3C1-4E6E-BC60-6DC8A6238003", "{autopf}\\Print Cost Calculator", "AppVersion",
                   "..\\dist\\PrintCostCalculator\\*", "PrintCostCalculator-{#AppVersion}-setup",
                   "PrivilegesRequired=admin", "x64compatible", "unchecked", "skipifsilent"):
        assert needle in s


def test_release_builds_and_smoke_tests_installer():
    s = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "-Installer" in s and "/VERYSILENT" in s and "unins000.exe" in s and "-setup.exe" in s


def test_build_script_installer_switch():
    s = (ROOT / "packaging/build_windows.ps1").read_text(encoding="utf-8")
    assert "[switch]$Installer" in s and "ISCC" in s and "LASTEXITCODE" in s


def test_changelog_030():
    assert "## 0.3.0 — 2026-10-19" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
