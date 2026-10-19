"""Home screen: searchable list of saved projects."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFile, Qt, QSize, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QMessageBox, QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from pcc.core.currency import format_money
from pcc.core.pricing import PricingError, compute_quote
from pcc.core.projects import (
    THUMBS_DIR, ProjectError, ProjectHandle, duplicate_project, list_projects,
    rename_project,
)
from pcc.gui.icons import icon

EMPTY_TEXT = "No projects yet — drop a sliced .3mf here or click ➕ New"
NO_MATCH_TEXT = "No projects match your search."
THUMB = 56
_NAME_ROLE = Qt.ItemDataRole.UserRole + 1
_FILTER_ROLE = Qt.ItemDataRole.UserRole + 2


def _label(text: str = "", muted: bool = False, bold: bool = False) -> QLabel:
    lab = QLabel(text)
    if muted:
        lab.setProperty("muted", True)
    if bold:
        f = lab.font()
        f.setBold(True)
        lab.setFont(f)
    lab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    return lab


def _first_thumbnail(handle: ProjectHandle) -> QPixmap | None:
    plates = handle.project.job.plates
    if not plates:
        return None
    pid = plates[0].id
    if not pid or any(c in pid for c in "/\\\x00") or pid in (".", ".."):
        return None
    pm = QPixmap(str(handle.path / THUMBS_DIR / f"{pid}.png"))
    return None if pm.isNull() else pm


class ProjectRow(QWidget):
    """One list row; the menu button reports back through ``menu_requested``."""

    def __init__(self, handle: ProjectHandle, price: str, thumb_pixmap: QPixmap | None):
        super().__init__()
        # Only the labels/thumbnail are mouse-transparent: clicks on them reach
        # the list (selection, double-click), while the ⋯ button stays clickable.
        p = handle.project
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 6, 8)
        row.setSpacing(14)
        self.has_thumbnail = thumb_pixmap is not None
        self.thumb_label = QLabel()
        self.thumb_label.setProperty("thumb", True)
        self.thumb_label.setFixedSize(THUMB, THUMB)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if thumb_pixmap is not None:
            pm = thumb_pixmap.scaled(
                THUMB * 2, THUMB * 2, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(2)
            self.thumb_label.setPixmap(pm)
        else:
            self.thumb_label.setPixmap(icon("printer", size=32).pixmap(32, 32))
        self.name_label = _label(p.name, bold=True)
        self.customer_label = _label(p.job.customer or "—", muted=True)
        n = len(p.job.plates)
        self.plates_label = _label(f"{n} plate" + ("" if n == 1 else "s"))
        self.price_label = _label(price, bold=True)
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.price_label.setMinimumWidth(110)
        self.edited_label = _label(_edited(p.updated_at), muted=True)
        self.edited_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.edited_label.setMinimumWidth(110)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addStretch(1)
        text.addWidget(self.name_label)
        text.addWidget(self.customer_label)
        text.addStretch(1)
        meta = QVBoxLayout()
        meta.setSpacing(2)
        meta.addStretch(1)
        meta.addWidget(self.price_label)
        meta.addWidget(self.plates_label, 0, Qt.AlignmentFlag.AlignRight)
        meta.addStretch(1)
        self.more_button = QToolButton()
        self.more_button.setText("⋯")
        self.more_button.setProperty("role", "more")
        self.more_button.setToolTip("More actions")
        self.more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_button.setFixedSize(36, 36)
        row.addWidget(self.thumb_label)
        row.addLayout(text, 1)
        row.addLayout(meta)
        row.addWidget(self.edited_label)
        row.addWidget(self.more_button)


def _edited(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    return f"edited {d.day} {d:%b %Y}"


class _ProjectList(QListWidget):
    """F2 renames and Delete deletes the current row."""

    rename_key = Signal()
    delete_key = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_F2 and not event.modifiers():
            self.rename_key.emit()
        elif event.matches(QKeySequence.StandardKey.Delete):
            self.delete_key.emit()
        else:
            super().keyPressEvent(event)


class ProjectsPage(QWidget):
    open_requested = Signal(Path)
    warnings_found = Signal(list)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self._names: dict[Path, str] = {}
        self._last_warnings: list[str] | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        title = QLabel("📁 Projects")
        title.setProperty("role", "title")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search name or customer")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(180)
        self.new_button = QPushButton("➕ New")
        self.new_button.setProperty("accent", True)
        self.import_button = QPushButton("📂 Import .3mf")
        bar.addWidget(title)
        bar.addSpacing(12)
        bar.addWidget(self.search_edit, 1)
        bar.addWidget(self.new_button)
        bar.addWidget(self.import_button)
        outer.addLayout(bar)
        self.list_widget = _ProjectList()
        self.list_widget.setObjectName("projects_list")
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setSpacing(2)
        self.empty_label = QLabel(EMPTY_TEXT)
        self.empty_label.setProperty("muted", True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        outer.addWidget(self.list_widget, 1)
        outer.addWidget(self.empty_label, 1)
        self.search_edit.textChanged.connect(self._apply_filter)
        self.list_widget.itemActivated.connect(self._activated)
        self.list_widget.customContextMenuRequested.connect(self._context_menu)
        self.list_widget.rename_key.connect(lambda: self._on_current(self.rename_project))
        self.list_widget.delete_key.connect(lambda: self._on_current(self.delete_project))
        state.projects_changed.connect(self.refresh)
        state.settings_changed.connect(self.refresh)
        state.catalog_changed.connect(self.refresh)
        # No scan here: the owner calls refresh() when the page is shown, after
        # it has connected warnings_found (else startup warnings are lost).

    # -- content ------------------------------------------------------
    def _price(self, handle: ProjectHandle) -> str:
        if not handle.project.job.plates:
            return "—"  # same as the editor: no plates, no quote
        try:
            q = compute_quote(handle.project.job, self.state.settings, self.state.catalog)
        except PricingError:
            return "—"
        return format_money(q.price, self.state.settings.currency_symbol)

    def refresh(self) -> None:
        handles, warnings = list_projects()
        lw = self.list_widget
        lw.clear()
        self._names = {}
        for h in handles:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, h.path)
            item.setData(_NAME_ROLE, h.project.name)
            item.setData(_FILTER_ROLE,
                         f"{h.project.name}\n{h.project.job.customer}".casefold())
            row = ProjectRow(h, self._price(h), _first_thumbnail(h))
            row.more_button.setMenu(self._menu_for(h.path, row.more_button))
            item.setSizeHint(QSize(0, row.sizeHint().height() + 8))
            lw.addItem(item)
            lw.setItemWidget(item, row)
            self._names[h.path] = h.project.name
        self._apply_filter()
        if warnings != self._last_warnings:  # a dismissed banner stays dismissed
            self._last_warnings = list(warnings)
            self.warnings_found.emit(list(warnings))

    def _apply_filter(self, *_) -> None:
        needle = self.search_edit.text().strip().casefold()
        shown = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            hide = bool(needle) and needle not in item.data(_FILTER_ROLE)
            item.setHidden(hide)
            shown += not hide
        total = self.list_widget.count()
        self.list_widget.setVisible(shown > 0)
        self.empty_label.setVisible(shown == 0)
        self.empty_label.setText(EMPTY_TEXT if total == 0 else NO_MATCH_TEXT)

    def _activated(self, item: QListWidgetItem) -> None:
        self.open_requested.emit(item.data(Qt.ItemDataRole.UserRole))

    # -- row actions --------------------------------------------------
    def _context_menu(self, pos) -> None:
        item = self.list_widget.itemAt(pos)
        if item is None or item.isHidden():
            return
        menu = self._menu_for(item.data(Qt.ItemDataRole.UserRole), self.list_widget)
        self._popup(menu, self.list_widget.viewport().mapToGlobal(pos))
        menu.deleteLater()

    def _popup(self, menu: QMenu, global_pos) -> None:
        menu.exec(global_pos)  # seam: tests replace the blocking popup

    def _on_current(self, action) -> None:
        item = self.list_widget.currentItem()
        if item is not None and not item.isHidden():
            action(item.data(Qt.ItemDataRole.UserRole))

    def _menu_for(self, path: Path, parent: QWidget) -> QMenu:
        menu = QMenu(parent)
        menu.addAction("Rename…", lambda: self.rename_project(path))
        menu.addAction("Duplicate", lambda: self.duplicate_project(path))
        menu.addAction("Show in folder", lambda: self.show_in_folder(path))
        menu.addSeparator()
        menu.addAction("Delete…", lambda: self.delete_project(path))
        return menu

    def _name_of(self, path: Path) -> str:
        return self._names.get(path, path.name)

    def rename_project(self, path: Path) -> None:
        old = self._name_of(path)
        name, ok = QInputDialog.getText(self, "Rename project", "Project name:", text=old)
        name = name.strip()
        if not ok or not name or name == old:
            return
        if self.state.project_path == path:
            # The open project lives in AppState: renaming through it keeps
            # state, header and window title in sync (it becomes dirty).
            self.state.rename_current(name)
            return
        try:
            rename_project(path, name)
        except (OSError, ProjectError) as e:
            QMessageBox.warning(self, "Couldn't rename", f"Couldn't rename '{old}': {e}")
            return
        self.state.projects_changed.emit()

    def duplicate_project(self, path: Path) -> None:
        try:
            duplicate_project(path, f"{self._name_of(path)} (copy)")
        except (OSError, ProjectError) as e:
            QMessageBox.warning(self, "Couldn't duplicate", f"Couldn't duplicate: {e}")
            return
        self.state.projects_changed.emit()

    def show_in_folder(self, path: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def delete_project(self, path: Path) -> None:
        name = self._name_of(path)
        ok = QMessageBox.question(
            self, "Delete project",
            f"Delete '{name}'? It will be moved to the Recycle Bin.")
        if ok != QMessageBox.StandardButton.Yes:
            return
        if not QFile.moveToTrash(str(path)):
            ok = QMessageBox.question(
                self, "Delete permanently?",
                f"Couldn't move '{name}' to the Recycle Bin. Delete permanently?")
            if ok != QMessageBox.StandardButton.Yes:
                return
            try:
                shutil.rmtree(path)
            except OSError as e:
                QMessageBox.warning(self, "Couldn't delete", f"Couldn't delete '{name}': {e}")
                return
        self.state.projects_changed.emit()
