"""Transient top-right (below the top bar/banner) notification with optional action buttons."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

_MARGIN = 20


class Toast(QFrame):
    def __init__(self, parent, anchor_top: Callable[[], int] | None = None):
        super().__init__(parent)
        self._anchor_top = anchor_top or (lambda: 0)
        self.setProperty("card", True)
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(16, 12, 12, 12)
        self._row.setSpacing(10)
        self.label = QLabel()
        self._row.addWidget(self.label)
        self._buttons: list[QPushButton] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        parent.installEventFilter(self)
        self.hide()

    def show_toast(self, text: str, actions: list[tuple[str, Callable]] | None = None,
                   ms: int = 6000) -> None:
        for b in self._buttons:
            self._row.removeWidget(b)
            b.deleteLater()
        self._buttons = []
        self.label.setText(text)
        for name, fn in actions or []:
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, f=fn: (f(), self.hide()))
            self._row.addWidget(b)
            self._buttons.append(b)
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        self._timer.start(ms)

    def _place(self) -> None:
        p = self.parentWidget()
        self.adjustSize()
        self.move(p.width() - self.width() - _MARGIN, self._anchor_top() + _MARGIN)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Resize and self.isVisible():
            self._place()
        return False
