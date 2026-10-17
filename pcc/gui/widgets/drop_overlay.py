"""Translucent overlay shown while .3mf files are dragged over the window."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from pcc.gui.theme import TOKENS, current_mode


class DropOverlay(QWidget):
    TEXT = "📂 Drop .3mf files to import"

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        parent.installEventFilter(self)
        self.hide()

    def show_overlay(self) -> None:
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Resize and self.isVisible():
            self.setGeometry(self.parentWidget().rect())
        return False

    def paintEvent(self, event) -> None:
        accent = QColor(TOKENS[current_mode()]["accent"])
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tint = QColor(accent)
        tint.setAlpha(60)
        r = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        p.setBrush(tint)
        pen = QPen(accent, 3, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(r, 14, 14)
        font = QFont(self.font())
        font.setPointSizeF(font.pointSizeF() + 6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(TOKENS[current_mode()]["text"]))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.TEXT)
        p.end()
