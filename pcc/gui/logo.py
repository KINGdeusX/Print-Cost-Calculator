"""Company logo: load/resize an image, store it as logo.jpg in the config dir."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter

from pcc.core.storage import config_dir

LOGO_MAX = 150
_ERROR = "Couldn't read that image."


class LogoError(Exception):
    pass


def load_logo_image(path: Path) -> bytes:
    """Read an image, fit it within LOGO_MAX, flatten onto white, return JPEG bytes."""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    img = reader.read()
    if img.isNull():
        raise LogoError(_ERROR)
    if img.width() > LOGO_MAX or img.height() > LOGO_MAX:
        img = img.scaled(
            LOGO_MAX, LOGO_MAX, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
    flat = QImage(img.size(), QImage.Format_RGB32)
    flat.fill(QColor("white"))
    painter = QPainter(flat)
    painter.drawImage(0, 0, img)
    painter.end()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    if not flat.save(buf, "JPEG", 90):
        raise LogoError(_ERROR)
    return bytes(ba)


def logo_path() -> Path:
    return config_dir() / "logo.jpg"


def save_logo(jpeg: bytes) -> None:
    path = logo_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "wb", dir=path.parent, delete=False, prefix=path.name + ".", suffix=".tmp"
    ) as tmp:
        tmp.write(jpeg)
    try:
        os.replace(tmp.name, path)
    except BaseException:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def remove_logo() -> None:
    try:
        logo_path().unlink()
    except FileNotFoundError:
        pass


def read_logo() -> bytes | None:
    """The stored logo, or None if missing or not a decodable image."""
    try:
        data = logo_path().read_bytes()
    except OSError:
        return None
    return data if not QImage.fromData(data).isNull() else None


def image_filter() -> str:
    exts = sorted(
        {bytes(f).decode("ascii", "ignore").lower() for f in QImageReader.supportedImageFormats()}
    )
    return "Images (" + " ".join(f"*.{e}" for e in exts if e) + ")"
