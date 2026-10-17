"""Dismissible warning / error banner."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class Banner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("banner", "warning")
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 10, 10)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.dismiss_button = QPushButton("✕")
        self.dismiss_button.setToolTip("Dismiss")
        self.dismiss_button.setFixedWidth(40)
        row.addWidget(self.label, 1)
        row.addWidget(self.dismiss_button, 0)
        self.dismiss_button.clicked.connect(self.hide)
        self.hide()

    def show_messages(self, level: str, lines: list[str]) -> None:
        level = level if level in ("warning", "danger") else "warning"
        self.setProperty("banner", level)
        self.style().unpolish(self)
        self.style().polish(self)
        prefix = "⛔ " if level == "danger" else "⚠️ "
        self.label.setText("\n".join(f"{prefix}{ln}" for ln in lines))
        self.show()
