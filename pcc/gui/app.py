"""GUI entry point. Keep module-level imports minimal: startup speed matters."""
from __future__ import annotations

import time

_T0 = time.perf_counter()  # before the PySide6 import: --timing is time-to-splash

import os  # noqa: E402
import sys  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402


def _selftest() -> int:
    """Packaging check: lazy imports and bundled assets are reachable."""
    import openpyxl  # noqa: F401

    import pcc.core.export_xlsx  # noqa: F401
    from pcc.gui.icons import app_icon

    if app_icon().isNull():
        print("selftest FAILED: app icon is null", file=sys.stderr)
        return 1
    problem = _selftest_logo_and_invoice()
    if problem:
        print(f"selftest FAILED: {problem}", file=sys.stderr)
        return 1
    print("selftest ok")
    return 0


def _selftest_logo_and_invoice() -> str | None:
    """JPEG encode/decode (imageformat plugins) and PDF output work in the bundle."""
    import datetime
    import tempfile
    from decimal import Decimal
    from pathlib import Path

    from PySide6.QtGui import QColor, QImage

    from pcc.core.invoice import InvoiceLine
    from pcc.gui import invoice_pdf, logo

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "logo.png"
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        img.fill(QColor("orange"))
        if not img.save(str(src), "PNG"):
            return "could not write a PNG"
        try:
            jpeg = logo.load_logo_image(src)
        except logo.LogoError as e:
            return f"logo: {e}"
        if QImage.fromData(jpeg).isNull():
            return "logo: JPEG does not decode"
        pdf = Path(tmp) / "invoice.pdf"
        try:
            invoice_pdf.render_invoice_pdf(
                pdf, company_name="Selftest", logo_jpeg=jpeg, number="INV-0001",
                date=datetime.date.today(), bill_to="",
                lines=[InvoiceLine("Print", 1, Decimal("1.00"), Decimal("1.00"))],
                currency_symbol="$")
            ok = pdf.read_bytes()[:4] == b"%PDF"
        except OSError:
            ok = False
        if not ok:
            return "invoice PDF was not written"
    return None


def wire_session(app, window, state) -> None:
    """Logoff/shutdown and quit must not lose a dirty project or pending settings."""
    from PySide6.QtCore import Qt

    # Qt asks for a direct connection: the session manager is only valid in the call
    app.commitDataRequest.connect(window.commit_session, Qt.ConnectionType.DirectConnection)
    app.aboutToQuit.connect(state.flush)


def main(argv: list[str] | None = None) -> int:
    t0 = _T0
    args = list(sys.argv[1:] if argv is None else argv)
    timing = "--timing" in args
    args = [a for a in args if a != "--timing"]

    def mark(stage: str) -> None:
        if timing:
            ms = (time.perf_counter() - t0) * 1000
            print(f"[timing] {stage}: {ms:.0f} ms", file=sys.stderr, flush=True)

    app = QApplication.instance() or QApplication([sys.argv[0], *args])
    app.setApplicationName("Print Cost Calculator")
    app.setOrganizationName("PrintCostCalculator")
    mark("qt")

    if os.environ.get("PCC_SELFTEST"):
        return _selftest()

    from pcc.gui.splash import Splash

    splash = Splash()
    splash.show()
    app.processEvents()
    mark("splash")

    splash.set_status("Loading settings…")
    from pcc.gui.icons import app_icon
    from pcc.gui.state import AppState
    from pcc.gui.theme import apply_theme

    app.setWindowIcon(app_icon())
    state = AppState()
    apply_theme(app, state.settings.theme)
    mark("state")

    splash.set_status("Building window…")
    from pcc.gui.main_window import MainWindow

    window = MainWindow(state)
    wire_session(app, window, state)
    mark("window")

    window.show()
    splash.finish(window)
    mark("shown")
    quit_ms = os.environ.get("PCC_EXIT_AFTER_SHOW", "")
    if quit_ms.isdigit():
        from PySide6.QtCore import QTimer

        QTimer.singleShot(int(quit_ms), app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
