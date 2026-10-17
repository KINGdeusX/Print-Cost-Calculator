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
    print("selftest ok")
    return 0


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
