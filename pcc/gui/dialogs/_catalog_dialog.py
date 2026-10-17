"""Shared list + form editor for printers and filaments (edits a deep copy)."""
from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QPushButton, QVBoxLayout, QWidget,
)

from pcc.gui.icons import app_icon
from pcc.gui.theme import TOKENS, current_mode
from pcc.gui.widgets.money_spin import no_drops


def muted(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("muted", True)
    lab.setWordWrap(True)
    return lab


class CatalogDialog(QDialog):
    """Subclasses define the item list, the form and the add/duplicate rules."""

    title = ""
    noun = ""

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.catalog = copy.deepcopy(state.catalog)
        self._loading = False
        self.setWindowTitle(self.title)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(640, 420)

        self.list = QListWidget()
        self.list.setMinimumWidth(200)
        self.add_button = QPushButton("➕ Add")
        self.duplicate_button = QPushButton("⧉ Duplicate")
        self.delete_button = QPushButton("🗑 Delete")
        self.add_button.setToolTip(f"Add a new {self.noun}")
        self.duplicate_button.setToolTip(f"Copy the selected {self.noun}")
        self.delete_button.setToolTip(
            f"Remove the selected {self.noun} (you always keep at least one)")
        btns = QHBoxLayout()
        for b in (self.add_button, self.duplicate_button, self.delete_button):
            btns.addWidget(b)
        left = QVBoxLayout()
        left.addWidget(self.list, 1)
        left.addLayout(btns)

        self.name_edit = QLineEdit()
        self.name_edit.setToolTip(f"The {self.noun}'s name (required)")
        no_drops(self.name_edit)
        self.error_label = QLabel("Name is required.")
        self.error_label.setStyleSheet(f"color: {TOKENS[current_mode()]['danger']};")
        self.error_label.setVisible(False)
        self.form = QFormLayout()
        self.form.setHorizontalSpacing(14)
        self.form.setVerticalSpacing(8)
        self.form.addRow("Name", self.name_edit)
        self.form.addRow(self.error_label)
        self.build_form()
        right = QVBoxLayout()
        self.form_host = QWidget()
        self.form_host.setLayout(self.form)
        right.addWidget(self.form_host)
        right.addStretch(1)

        top = QHBoxLayout()
        top.setSpacing(16)
        top.addLayout(left, 2)
        top.addLayout(right, 3)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setProperty("accent", True)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        col = QVBoxLayout(self)
        col.addLayout(top, 1)
        col.addWidget(self.buttons)

        self.list.currentRowChanged.connect(self._on_row)
        self.add_button.clicked.connect(self._add)
        self.duplicate_button.clicked.connect(self._duplicate)
        self.delete_button.clicked.connect(self._delete)
        self.name_edit.textEdited.connect(self._on_name)
        self._rebuild_list(0)

    # -- hooks ----------------------------------------------------------
    def items(self) -> list:
        raise NotImplementedError

    def build_form(self) -> None:
        raise NotImplementedError

    def new_item(self):
        raise NotImplementedError

    def clone_item(self, item):
        raise NotImplementedError

    def can_delete(self, item) -> bool:
        raise NotImplementedError

    def load_form(self, item) -> None:
        raise NotImplementedError

    def decorate(self, row, item) -> None:
        """Set text/icon of a list row."""
        row.setText(item.name or "(unnamed)")

    # -- list handling ----------------------------------------------------
    def current_item(self):
        r = self.list.currentRow()
        items = self.items()
        return items[r] if 0 <= r < len(items) else None

    def _rebuild_list(self, select: int) -> None:
        self._loading = True
        self.list.clear()
        for it in self.items():
            self.list.addItem("")
            self.decorate(self.list.item(self.list.count() - 1), it)
        self._loading = False
        self.list.setCurrentRow(max(0, min(select, self.list.count() - 1)))
        self._on_row(self.list.currentRow())

    def refresh_row(self) -> None:
        it = self.current_item()
        if it is not None:
            self.decorate(self.list.currentItem(), it)

    def _on_row(self, _row: int) -> None:
        if self._loading:
            return
        it = self.current_item()
        self._loading = True
        self.form_host.setEnabled(it is not None)
        if it is not None:
            self.name_edit.setText(it.name)
            self.load_form(it)
        self._loading = False
        self.delete_button.setEnabled(it is not None and self.can_delete(it))
        self.duplicate_button.setEnabled(it is not None)
        self._validate()

    def _on_name(self, text: str) -> None:
        it = self.current_item()
        if it is not None and not self._loading:
            it.name = text.strip()
            self.refresh_row()
            self._validate()

    def _validate(self) -> None:
        ok = all(it.name.strip() for it in self.items())
        cur = self.current_item()
        self.error_label.setVisible(cur is not None and not cur.name.strip())
        self.ok_button.setEnabled(ok)

    def _add(self) -> None:
        self.items().append(self.new_item())
        self._rebuild_list(len(self.items()) - 1)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _duplicate(self) -> None:
        it = self.current_item()
        if it is None:
            return
        items = self.items()
        items.insert(items.index(it) + 1, self.clone_item(it))
        self._rebuild_list(items.index(it) + 1)

    def _delete(self) -> None:
        it = self.current_item()
        if it is None or not self.can_delete(it):
            return
        row = self.list.currentRow()
        self.items().remove(it)
        self.after_delete(it)
        self._rebuild_list(row)

    def after_delete(self, item) -> None:
        pass

    def accept(self) -> None:
        if not self.ok_button.isEnabled():
            return
        self.state.set_catalog(self.catalog)
        super().accept()
