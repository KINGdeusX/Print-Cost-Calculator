"""Where user data lives: Documents/Print Cost Calculator/{Projects,Invoices}."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_APP_FOLDER = "Print Cost Calculator"
_XDG_RE = re.compile(r'^\s*XDG_DOCUMENTS_DIR\s*=\s*"?([^"\n]*)"?\s*$', re.M)


def linux_documents_dir(home: Path, user_dirs_text: str | None) -> Path:
    """Resolve the Documents folder from user-dirs.dirs text; `~/Documents` fallback."""
    fallback = home / "Documents"
    if not user_dirs_text:
        return fallback
    m = _XDG_RE.search(user_dirs_text)
    if not m:
        return fallback
    raw = m.group(1).strip().replace("$HOME", str(home))
    if not raw:
        return fallback
    path = Path(raw)
    if not path.is_absolute() or path == home:
        return fallback
    return path


def _windows_documents_dir() -> Path | None:
    """Known-folder lookup (handles OneDrive redirection); None on any failure."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
        guid = GUID(0xFDD39AD0, 0x238F, 0x46AF,
                    (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
        buf = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_wchar_p)]
        hr = shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(buf))
        try:
            if hr != 0 or not buf.value:
                return None
            return Path(buf.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(buf)
    except Exception:
        return None


def documents_dir() -> Path:
    home = Path.home()
    if sys.platform == "win32":
        return _windows_documents_dir() or home / "Documents"
    if sys.platform.startswith("linux"):
        base = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
        try:
            text = (base / "user-dirs.dirs").read_text(encoding="utf-8")
        except (OSError, ValueError):
            text = None
        return linux_documents_dir(home, text)
    return home / "Documents"


def data_root() -> Path:
    env = os.environ.get("PCC_DATA_DIR")
    if env:
        return Path(env)
    return documents_dir() / _APP_FOLDER


def _sub(name: str) -> Path:
    p = data_root() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def projects_dir() -> Path:
    return _sub("Projects")


def invoices_dir() -> Path:
    return _sub("Invoices")
