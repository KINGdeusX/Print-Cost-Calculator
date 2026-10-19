"""Editor header: Back / Save, editable project name, unsaved-changes marker."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget


class ProjectHeader(QFrame):
    back_requested = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setProperty("card", True)
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(12, 8, 12, 8)
        self._row.setSpacing(8)
        self.back_button = QPushButton("⬅ Back")
        self.back_button.setToolTip("Back to projects (Alt+Left)")
        self.save_button = QPushButton("💾 Save")
        self.save_button.setProperty("accent", True)
        self.save_button.setToolTip("Save project (Ctrl+S)")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Project name")
        self.name_edit.setToolTip("Project name")
        self.name_edit.setMinimumWidth(160)
        self.name_edit.setMaximumWidth(340)
        self.dirty_label = QLabel("● Unsaved changes")
        self.dirty_label.setProperty("dirty", True)
        for w in (self.back_button, self.save_button):
            self._row.addWidget(w)
        self._row.addWidget(self.name_edit, 1)
        self._row.addWidget(self.dirty_label)
        self._row.addStretch(1)
        self.back_button.clicked.connect(self.back_requested)
        self.name_edit.editingFinished.connect(self._commit_name)
        state.dirty_changed.connect(self._sync_dirty)
        state.project_opened.connect(self.refresh)
        state.project_closed.connect(self.refresh)
        state.project_renamed.connect(lambda _name: self.refresh())
        self.refresh()

    def add_trailing(self, widget: QWidget) -> None:
        """Right-aligned slot (the printer picker lives here)."""
        self._row.addWidget(widget)

    def refresh(self) -> None:
        project = self.state.project
        if project is not None and self.name_edit.text() != project.name:
            self.name_edit.setText(project.name)
        elif project is None:
            self.name_edit.clear()
        self._sync_dirty(self.state.dirty)

    def _sync_dirty(self, dirty: bool) -> None:
        dirty = bool(dirty) and self.state.project is not None
        self.dirty_label.setVisible(dirty)
        self.save_button.setEnabled(dirty)

    def _commit_name(self) -> None:
        project = self.state.project
        if project is None:
            return
        text = self.name_edit.text().strip()
        if not text:
            self.name_edit.setText(project.name)  # never leave a project unnamed
        elif text != project.name:
            self.state.rename_current(text)
