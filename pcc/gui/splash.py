"""Startup splash painted with QPainter (no image assets besides icon.svg)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QSplashScreen

from pcc import __version__

_ICON = Path(__file__).resolve().parent.parent / "assets" / "icon.svg"
W, H = 480, 280
_CARD = QColor("#1F2227")
_TEXT = QColor("#ECEAE6")
_MUTED = QColor("#A4A9B1")
_ACCENT = QColor("#FF8A3D")


class Splash(QSplashScreen):
    def __init__(self):
        self._status = "Starting…"
        screen = QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen is not None else 0.0
        self._dpr = dpr if dpr > 0 else 2.0
        super().__init__(self._paint())
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

    def _paint(self) -> QPixmap:
        pm = QPixmap(int(W * self._dpr), int(H * self._dpr))
        pm.setDevicePixelRatio(self._dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        card = QPainterPath()
        card.addRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), 14, 14)
        p.fillPath(card, _CARD)
        p.setClipPath(card)
        p.fillRect(QRectF(0, 0, 8, H), _ACCENT)
        p.setClipping(False)
        try:
            r = QSvgRenderer(QByteArray(_ICON.read_bytes()))
            if r.isValid():
                r.render(p, QRectF(40, 56, 96, 96))
        except OSError:
            pass
        title = QFont("Segoe UI", 20)
        title.setBold(True)
        p.setFont(title)
        p.setPen(_TEXT)
        p.drawText(QRectF(156, 60, W - 176, 48), Qt.AlignmentFlag.AlignVCenter,
                   "Print Cost Calculator")
        p.setFont(QFont("Segoe UI", 11))
        p.setPen(_MUTED)
        p.drawText(QRectF(156, 110, W - 176, 28), Qt.AlignmentFlag.AlignVCenter,
                   f"v{__version__}")
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRectF(40, H - 56, W - 80, 28),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._status)
        p.end()
        return pm

    def set_status(self, text: str) -> None:
        self._status = text
        self.setPixmap(self._paint())
        self.repaint()
        QApplication.processEvents()
