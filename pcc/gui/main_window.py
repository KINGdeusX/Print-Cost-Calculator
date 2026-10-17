"""Main window shell: top bar, responsive three-area layout, status bar."""
from __future__ import annotations

import base64
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QFileDialog, QMainWindow, QMessageBox, QScrollArea, QSplitter, QToolButton, QVBoxLayout, QWidget,
)

from pcc.core.currency import CURRENCIES
from pcc.gui.icons import app_icon, icon
from pcc.gui.state import AppState
from pcc.gui.theme import apply_theme, current_mode, resolve_mode
from pcc.gui.widgets.banner import Banner
from pcc.gui.widgets.drop_overlay import DropOverlay
from pcc.gui.widgets.job_panel import JobPanel
from pcc.gui.widgets.plates_view import PlatesView
from pcc.gui.widgets.summary_panel import SummaryPanel
from pcc.gui.widgets.toast import Toast

COMPACT_WIDTH = 1000
_THEMES = ("system", "light", "dark")
_CUSTOM = "Custom…"


def _area(name: str) -> QWidget:
    w = QWidget()
    w.setObjectName(name)
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    return w


def _scrolled(panel: QWidget) -> QScrollArea:
    """Let a panel scroll instead of overlapping when the window is small."""
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setWidget(panel)
    return sa


class MainWindow(QMainWindow):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setWindowTitle("Print Cost Calculator")
        self.setWindowIcon(app_icon())
        # explicit floor: below COMPACT_WIDTH the compact layout needs far less
        # than the three-column layout does, so do not inherit its minimum
        self.setMinimumSize(640, 460)
        self.job_area = _area("job_area")
        self.plates_area = _area("plates_area")
        self.summary_area = _area("summary_area")
        self.job_area.setMaximumWidth(280)
        self._compact: bool | None = None

        root = QWidget()
        col = QVBoxLayout(root)
        col.setContentsMargins(12, 12, 12, 12)
        col.setSpacing(12)
        col.addWidget(self._build_top_bar())
        self.banner = Banner()
        col.addWidget(self.banner)
        self._build_splitters()
        col.addWidget(self._wide, 1)
        col.addWidget(self._narrow, 1)
        self.setCentralWidget(root)
        self._apply_layout(False)

        self.job_panel = JobPanel(state)
        self.plates_view = PlatesView(state)
        self.summary = SummaryPanel(state)
        self.job_area.layout().addWidget(_scrolled(self.job_panel))
        self.plates_area.layout().addWidget(self.plates_view)
        self.summary_area.layout().addWidget(_scrolled(self.summary))
        self.plates_view.import_requested.connect(self.import_dialog)
        self._import_warnings: list[str] | None = None
        self.toast = Toast(root, anchor_top=self._content_top)
        self.drop_overlay = DropOverlay(root)
        self.setAcceptDrops(True)
        QShortcut(QKeySequence.StandardKey.Open, self, activated=self.import_dialog)
        QShortcut(QKeySequence.StandardKey.New, self, activated=self.new_job)

        self._refresh_printers()
        self._refresh_currency()
        self._refresh_theme_button()
        state.catalog_changed.connect(self._refresh_printers)
        state.job_changed.connect(self._sync_printer_selection)
        state.settings_changed.connect(self._refresh_currency)
        state.settings_changed.connect(self._refresh_theme_button)
        state.warning.connect(self._on_warning)
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
        summary.setMaximumWidth(16777215 if compact else 360)
        if compact:
            self._narrow_top.addWidget(job)
            self._narrow_top.addWidget(plates)
            self._narrow.addWidget(summary)
            self._narrow_top.setStretchFactor(0, 0)
            self._narrow_top.setStretchFactor(1, 1)
            self._narrow.setStretchFactor(0, 2)
            self._narrow.setStretchFactor(1, 1)
            self._narrow_top.setSizes([240, 600])
            self._narrow.setSizes([200, 100])
        else:
            for i, w in enumerate((job, plates, summary)):
                self._wide.insertWidget(i, w)
            for i, s in enumerate((0, 1, 0)):
                self._wide.setStretchFactor(i, s)
            self._wide.setSizes([270, 640, 340])
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
        self.banner.show_messages("warning", lines)

    # -- import / new job ---------------------------------------------
    def import_dialog(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(
            self, "Import sliced files", "", "Sliced 3MF (*.3mf)")
        if names:
            self.import_files([Path(n) for n in names])

    def _content_top(self) -> int:
        area = self._narrow if self.is_compact() else self._wide
        return area.geometry().top()

    def _on_warning(self, msg: str) -> None:
        if self._import_warnings is not None:
            self._import_warnings.append(msg)
        else:
            self.show_warnings([msg])

    def import_files(self, paths: list[Path]) -> None:
        self.banner.hide()
        before = len(self.state.job.plates)
        self._import_warnings = []
        try:
            failures = self.state.import_files([Path(p) for p in paths])
        finally:
            warnings, self._import_warnings = self._import_warnings, None
        added = len(self.state.job.plates) - before
        lines = [f"{n}: {r}" for n, r in failures] + warnings
        if lines:
            all_failed = bool(failures) and len(failures) == len(paths)
            self.banner.show_messages("danger" if all_failed else "warning", lines)
        if added > 0:
            self.toast.show_toast(f"✅ Imported {added} plate(s)")

    def new_job(self) -> None:
        if self.state.job.plates:
            ok = QMessageBox.question(
                self, "New job", "Start a new job? Current plates will be cleared.")
            if ok != QMessageBox.StandardButton.Yes:
                return
        self.state.new_job()

    # -- drag and drop --------------------------------------------------
    @staticmethod
    def _dropped_3mf(mime) -> list[Path]:
        out = []
        for url in mime.urls():
            if url.isLocalFile() and url.toLocalFile().lower().endswith(".3mf"):
                out.append(Path(url.toLocalFile()))
        return out

    def dragEnterEvent(self, event) -> None:
        if self._dropped_3mf(event.mimeData()):
            event.acceptProposedAction()
            self.drop_overlay.show_overlay()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._dropped_3mf(event.mimeData()):
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self.drop_overlay.hide()

    def dropEvent(self, event) -> None:
        self.drop_overlay.hide()
        paths = self._dropped_3mf(event.mimeData())
        if paths:
            event.acceptProposedAction()
            self.import_files(paths)

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
