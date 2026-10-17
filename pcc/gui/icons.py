"""SVG icon loading: recolors ``currentColor`` and renders crisp pixmaps."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent.parent / "assets"
_DPR = 2
_APP_SIZES = (16, 32, 48, 64, 128, 256)


def _render(svg: bytes, size: int) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg))
    pm = QPixmap(size * _DPR, size * _DPR)
    pm.fill(Qt.GlobalColor.transparent)
    if renderer.isValid():
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(p, QRectF(0, 0, size * _DPR, size * _DPR))
        p.end()
    pm.setDevicePixelRatio(_DPR)
    return pm


@lru_cache(maxsize=None)
def _icon(name: str, color: str | None, size: int) -> QIcon:
    path = ASSETS / "icons" / f"{name}.svg"
    try:
        svg = path.read_text(encoding="utf-8")
    except OSError:
        return QIcon()
    svg = svg.replace("currentColor", color or "#000000")
    pm = _render(svg.encode("utf-8"), size)
    return QIcon() if pm.isNull() else QIcon(pm)


def icon(name: str, color: str | None = None, size: int = 20) -> QIcon:
    return _icon(name, color, size)


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    ic = QIcon()
    try:
        svg = (ASSETS / "icon.svg").read_bytes()
        if QSvgRenderer(QByteArray(svg)).isValid():
            for s in _APP_SIZES:
                pm = _render(svg, s)
                pm.setDevicePixelRatio(1)  # report true pixel size
                ic.addPixmap(pm)
            return ic
    except OSError:
        pass
    return QIcon(str(ASSETS / "icon.png"))
