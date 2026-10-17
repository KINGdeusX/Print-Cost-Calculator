"""Export menu and save/append flow for the Excel report."""
from __future__ import annotations

import zipfile
from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox

_FILTER = "Excel (*.xlsx)"


class ExportFlow(QObject):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self._menu = QMenu(parent if hasattr(parent, "windowTitle") else None)
        self.new_action = self._menu.addAction("📄 New report…")
        self.append_action = self._menu.addAction("➕ Append to existing…")
        self.last_action = self._menu.addAction("↻ Append to last")
        self.new_action.triggered.connect(self.new_report)
        self.append_action.triggered.connect(self.append_existing)
        self.last_action.triggered.connect(self.append_last)
        self._menu.aboutToShow.connect(self.refresh_menu)
        self.refresh_menu()

    def menu(self) -> QMenu:
        return self._menu

    # -- helpers ------------------------------------------------------
    def _last(self) -> Path | None:
        raw = self.state.settings.last_export_path
        return Path(raw) if raw else None

    def has_last(self) -> bool:
        p = self._last()
        return p is not None and p.exists()

    def refresh_menu(self) -> None:
        p = self._last()
        if p is None:
            self.last_action.setText("↻ Append to last")
        else:
            self.last_action.setText(f"↻ Append to last ({p.name})")
        self.last_action.setEnabled(self.has_last())

    def _start_dir(self) -> str:
        p = self._last()
        return str(p.parent) if p is not None else str(Path.home())

    def _parent_widget(self):
        return self.parent()

    # -- actions ------------------------------------------------------
    def new_report(self) -> bool:
        if self.state.quote is None:
            return False
        name, _ = QFileDialog.getSaveFileName(
            self._parent_widget(), "Save report", self._start_dir(), _FILTER)
        return bool(name) and self.export(Path(name), append=False)

    def append_existing(self) -> bool:
        if self.state.quote is None:
            return False
        name, _ = QFileDialog.getOpenFileName(
            self._parent_widget(), "Append to existing report", self._start_dir(), _FILTER)
        return bool(name) and self.export(Path(name), append=True)

    def append_last(self) -> bool:
        if self.state.quote is None or not self.has_last():
            return False
        return self.export(self._last(), append=True)

    def quick_export(self) -> bool:
        """Ctrl+E: append to last if available, else a new report."""
        if self.state.quote is None:
            return False
        return self.append_last() if self.has_last() else self.new_report()

    def export(self, path: Path, append: bool) -> bool:
        from openpyxl.utils.exceptions import InvalidFileException

        from pcc.core import export_xlsx

        parent = self._parent_widget()
        while True:
            try:
                written = export_xlsx.export_quote(
                    Path(path), self.state.job, self.state.quote,
                    self.state.catalog, append=append)
                break
            except PermissionError:
                box = QMessageBox(
                    QMessageBox.Icon.Warning, "File is open",
                    "Close the file in Excel, then retry",
                    QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel,
                    parent)
                if box.exec() != QMessageBox.StandardButton.Retry:
                    return False
            except (OSError, zipfile.BadZipFile, InvalidFileException,
                    KeyError, ValueError) as e:
                QMessageBox.critical(parent, "Export failed",
                                     f"Could not save the report: {e}")
                return False
        written = Path(written)
        self.state.update_settings(last_export_path=str(written))
        self._toast(written)
        return True

    def _toast(self, written: Path) -> None:
        parent = self._parent_widget()
        win = parent.window() if parent is not None and hasattr(parent, "window") else None
        toast = getattr(win, "toast", None)
        if toast is None:
            return
        toast.show_toast(
            f"✅ Saved to {written.name}",
            [("Open file", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(written)))),
             ("Open folder", lambda: QDesktopServices.openUrl(
                 QUrl.fromLocalFile(str(written.parent))))])
