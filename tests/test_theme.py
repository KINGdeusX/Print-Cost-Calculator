from pathlib import Path

import pytest

from pcc.gui.icons import app_icon, icon
from pcc.gui.theme import TOKENS, apply_theme, build_qss, resolve_mode

ICON_DIR = Path(__file__).resolve().parent.parent / "pcc" / "assets" / "icons"


def _lum(hex_color):
    h = hex_color.lstrip("#")
    chans = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        chans.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * chans[0] + 0.7152 * chans[1] + 0.0722 * chans[2]


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_token_sets_match():
    assert TOKENS["light"].keys() == TOKENS["dark"].keys()
    assert set(TOKENS["light"]) == {
        "bg", "surface", "surface2", "border", "text", "text_muted",
        "accent", "accent_text", "success", "warning", "danger",
    }


def test_qss_uses_tokens():
    assert TOKENS["dark"]["accent"] in build_qss("dark")
    assert TOKENS["light"]["bg"] in build_qss("light")
    assert 'QFrame[card="true"]' in build_qss("light")


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_contrast(mode):
    t = TOKENS[mode]
    assert contrast(t["text"], t["surface"]) >= 4.5
    assert contrast(t["text_muted"], t["surface"]) >= 4.5
    assert contrast(t["accent_text"], t["accent"]) >= 4.5


def test_icon_loads(qapp):
    assert not icon("sun", "#ff0000").isNull()


def test_icon_recolors(qapp):
    img = icon("plus", "#ff0000", 24).pixmap(24, 24).toImage()
    px = [img.pixelColor(x, y) for x in range(img.width()) for y in range(img.height())]
    assert any(c.alpha() > 200 and c.red() > 200 and c.green() < 60 for c in px)


def test_every_icon_file_renders(qapp):
    files = sorted(ICON_DIR.glob("*.svg"))
    assert len(files) >= 14
    for f in files:
        assert not icon(f.stem, "#000000").pixmap(20, 20).isNull(), f.name


def test_app_icon(qapp):
    ic = app_icon()
    assert not ic.isNull()
    assert 256 in [s.width() for s in ic.availableSizes()]


def test_apply_theme(qapp):
    assert apply_theme(qapp, "dark") == "dark"
    assert qapp.styleSheet() == build_qss("dark")
    assert apply_theme(qapp, "light") == "light"
    assert apply_theme(qapp, "system") in ("light", "dark")
    assert resolve_mode("dark", qapp) == "dark"


def test_qss_chevron_urls_quoted_posix():
    import re

    for mode in ("light", "dark"):
        urls = re.findall(r"url\((.*?)\)", build_qss(mode))
        assert len(urls) == 4
        for u in urls:
            assert u.startswith('"') and u.endswith('"')
            assert "\\" not in u
            assert Path(u.strip('"')).is_file()


def test_icon_default_color_follows_theme(qapp):
    apply_theme(qapp, "dark")
    img = icon("sun").pixmap(20, 20).toImage()
    want = TOKENS["dark"]["text"].lstrip("#").upper()
    hits = [c for c in (img.pixelColor(x, y) for x in range(img.width()) for y in range(img.height())) if c.alpha() == 255]
    assert hits and all(c.name().lstrip("#").upper() == want for c in hits)
