"""Main window shell: top bar, responsive three-area layout, status bar."""
from __future__ import annotations

import base64

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QMainWindow, QSplitter, QToolButton, QVBoxLayout, QWidget,
)

from pcc.core.currency import CURRENCIES
from pcc.gui.icons import app_icon, icon
from pcc.gui.state import AppState
from pcc.gui.theme import apply_theme, current_mode, resolve_mode

COMPACT_WIDTH = 1000
_THEMES = ("system", "light", "dark")
_CUSTOM = "Custom…"


def _area(name: str) -> QWidget:
    w = QWidget()
    w.setObjectName(name)
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    return w


class MainWindow(QMainWindow):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setWindowTitle("Print Cost Calculator")
        self.setWindowIcon(app_icon())
        self.job_area = _area("job_area")
        self.plates_area = _area("plates_area")
        self.summary_area = _area("summary_area")
        self._compact: bool | None = None

        root = QWidget()
        col = QVBoxLayout(root)
        col.setContentsMargins(12, 12, 12, 12)
        col.setSpacing(12)
        col.addWidget(self._build_top_bar())
        self._build_splitters()
        col.addWidget(self._wide, 1)
        col.addWidget(self._narrow, 1)
        self.setCentralWidget(root)
        self._apply_layout(False)

        self._refresh_printers()
        self._refresh_currency()
        self._refresh_theme_button()
        state.catalog_changed.connect(self._refresh_printers)
        state.job_changed.connect(self._sync_printer_selection)
        state.settings_changed.connect(self._refresh_currency)
        state.settings_changed.connect(self._refresh_theme_button)
        state.warning.connect(lambda msg: self.show_warnings([msg]))
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_scheme)

        self._restore_geometry()
        if state.pending_warnings:
            self.show_warnings(list(state.pending_warnings))

    # -- construction -------------------------------------------------
    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setProperty("card", True)
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)
        self._title_icon = QLabel()
        self._title_icon.setPixmap(app_icon().pixmap(24, 24))
        title = QLabel("Print Cost Calculator")
        f = title.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() + 2)
        title.setFont(f)
        row.addWidget(self._title_icon)
        row.addWidget(title)
        row.addStretch(1)
        self.printer_combo = QComboBox()
        self.printer_combo.setToolTip("Printer for this job")
        self.printer_combo.setMinimumWidth(200)
        self.currency_combo = QComboBox()
        self.currency_combo.setToolTip("Currency")
        self.theme_button = QToolButton()
        self.settings_button = QToolButton()
        self.settings_button.setToolTip("Settings")
        self.settings_button.setIcon(icon("settings"))
        for w in (self.printer_combo, self.currency_combo,
                  self.theme_button, self.settings_button):
            row.addWidget(w)
        self.printer_combo.currentIndexChanged.connect(self._on_printer)
        self.currency_combo.currentIndexChanged.connect(self._on_currency)
        self.theme_button.clicked.connect(self._cycle_theme)
        return bar

    def _build_splitters(self) -> None:
        self._wide = QSplitter(Qt.Orientation.Horizontal)
        self._narrow = QSplitter(Qt.Orientation.Vertical)
        self._narrow_top = QSplitter(Qt.Orientation.Horizontal)
        self._narrow.addWidget(self._narrow_top)
        for s in (self._wide, self._narrow, self._narrow_top):
            s.setChildrenCollapsible(False)
            s.setHandleWidth(10)

    def _apply_layout(self, compact: bool) -> None:
        if compact == self._compact:
            return
        self._compact = compact
        job, plates, summary = self.job_area, self.plates_area, self.summary_area
        if compact:
            self._narrow_top.addWidget(job)
            self._narrow_top.addWidget(plates)
            self._narrow.addWidget(summary)
            self._narrow_top.setStretchFactor(0, 1)
            self._narrow_top.setStretchFactor(1, 2)
            self._narrow.setStretchFactor(0, 2)
            self._narrow.setStretchFactor(1, 1)
            self._narrow_top.setSizes([100, 200])
            self._narrow.setSizes([200, 100])
        else:
            for i, w in enumerate((job, plates, summary)):
                self._wide.insertWidget(i, w)
            for i, s in enumerate((10, 20, 12)):
                self._wide.setStretchFactor(i, s)
            self._wide.setSizes([100, 200, 120])
        self._wide.setVisible(not compact)
        self._narrow.setVisible(compact)

    def is_compact(self) -> bool:
        self._apply_layout(self.width() < COMPACT_WIDTH)  # hidden windows get no resizeEvent
        return bool(self._compact)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_layout(event.size().width() < COMPACT_WIDTH)

    # -- printer / currency ------------------------------------------
    def _refresh_printers(self) -> None:
        c = self.printer_combo
        c.blockSignals(True)
        c.clear()
        for p in self.state.catalog.printers:
            c.addItem(p.name, p.id)
        c.blockSignals(False)
        self._sync_printer_selection()

    def _sync_printer_selection(self) -> None:
        c = self.printer_combo
        i = c.findData(self.state.job.printer_id)
        if i >= 0 and i != c.currentIndex():
            c.blockSignals(True)
            c.setCurrentIndex(i)
            c.blockSignals(False)

    def _on_printer(self, index: int) -> None:
        pid = self.printer_combo.itemData(index)
        if pid:
            self.state.update_job(printer_id=pid)

    def _refresh_currency(self) -> None:
        s = self.state.settings
        c = self.currency_combo
        c.blockSignals(True)
        c.clear()
        known = set()
        for code, sym, name in CURRENCIES:
            c.addItem(f"{sym} {code}", code)
            c.setItemData(c.count() - 1, name, Qt.ItemDataRole.ToolTipRole)
            known.add(code)
        if s.currency_code not in known:
            c.addItem(f"{s.currency_symbol} {s.currency_code}", s.currency_code)
        c.addItem(_CUSTOM, None)
        c.setCurrentIndex(c.findData(s.currency_code))
        c.blockSignals(False)

    def _on_currency(self, index: int) -> None:
        code = self.currency_combo.itemData(index)
        if code is None:
            sym, ok = QInputDialog.getText(
                self, "Custom currency", "Currency symbol:",
                text=self.state.settings.currency_symbol)
            sym = sym.strip()
            if ok and sym:
                self.state.update_settings(currency_code="XXX", currency_symbol=sym)
            else:
                self._refresh_currency()
            return
        sym = next(s for c, s, _ in CURRENCIES if c == code) if any(
            c == code for c, _, _ in CURRENCIES) else self.state.settings.currency_symbol
        self.state.update_settings(currency_code=code, currency_symbol=sym)

    # -- theme --------------------------------------------------------
    def _cycle_theme(self) -> None:
        cur = self.state.settings.theme
        nxt = _THEMES[(_THEMES.index(cur) + 1) % 3] if cur in _THEMES else "system"
        self.state.update_settings(theme=nxt)
        apply_theme(QApplication.instance(), nxt)
        self._refresh_theme_button()

    def _on_scheme(self, *_) -> None:
        if self.state.settings.theme == "system":
            apply_theme(QApplication.instance(), "system")
            self._refresh_theme_button()

    def _refresh_theme_button(self) -> None:
        theme = self.state.settings.theme
        mode = resolve_mode(theme, QApplication.instance())
        self.theme_button.setIcon(icon("sun" if mode == "light" else "moon"))
        self.theme_button.setToolTip(f"Theme: {theme.capitalize()}")
        self.settings_button.setIcon(icon("settings"))

    # -- warnings -----------------------------------------------------
    def show_warnings(self, lines: list[str]) -> None:
        self.statusBar().showMessage("; ".join(lines))

    # -- geometry -----------------------------------------------------
    def _restore_geometry(self) -> None:
        raw = self.state.settings.window_geometry
        ok = False
        if raw:
            try:
                ok = self.restoreGeometry(QByteArray(base64.b64decode(raw)))
            except Exception:
                ok = False
        if not ok:
            self.resize(1280, 800)
            screen = self.screen()
            if screen is not None:
                self.move(screen.availableGeometry().center() - self.rect().center())

    def closeEvent(self, event) -> None:
        geo = bytes(self.saveGeometry())
        self.state.update_settings(window_geometry=base64.b64encode(geo).decode("ascii"))
        self.state.flush()
        super().closeEvent(event)
