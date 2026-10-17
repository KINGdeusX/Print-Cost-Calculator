"""Render pcc/assets/icon.svg to icon.png (256) and a multi-size icon.ico.

Run: .venv/bin/python packaging/make_icons.py
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "pcc" / "assets"
ICO_SIZES = (16, 32, 48, 64, 128, 256)


def render(renderer: QSvgRenderer, size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(p)
    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba.data())


def write_ico(path: Path, images: dict[int, bytes]) -> None:
    """ICO container with PNG-encoded entries (valid for Windows Vista+)."""
    n = len(images)
    out = struct.pack("<HHH", 0, 1, n)
    offset = 6 + 16 * n
    body = b""
    for size, data in images.items():
        dim = 0 if size >= 256 else size
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        body += data
    path.write_bytes(out + body)


def main() -> int:
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    renderer = QSvgRenderer(str(ASSETS / "icon.svg"))
    if not renderer.isValid():
        print("icon.svg failed to load", file=sys.stderr)
        return 1
    pngs = {s: png_bytes(render(renderer, s)) for s in ICO_SIZES}
    (ASSETS / "icon.png").write_bytes(pngs[256])
    write_ico(ASSETS / "icon.ico", pngs)
    print(f"wrote icon.png and icon.ico ({', '.join(map(str, ICO_SIZES))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
