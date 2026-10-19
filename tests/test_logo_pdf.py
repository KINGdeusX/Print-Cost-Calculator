from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QImage

from pcc.core.invoice import InvoiceLine
from pcc.gui.invoice_pdf import invoice_html, render_invoice_pdf
from pcc.gui.logo import (
    LogoError,
    image_filter,
    load_logo_image,
    logo_path,
    read_logo,
    remove_logo,
    save_logo,
)


def _jpeg(w=60, h=30) -> bytes:
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("#336699"))
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "JPEG")
    return bytes(ba)


def test_logo_large_rgba_png_resized_flattened(tmp_path, qapp):
    src = tmp_path / "big.png"
    img = QImage(600, 300, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    img.save(str(src))
    data = load_logo_image(src)
    out = QImage.fromData(data)
    assert data[:3] == b"\xff\xd8\xff" and (out.width(), out.height()) == (150, 75)
    assert QColor(out.pixel(10, 10)).name() == "#ffffff"


def test_logo_small_not_upscaled(tmp_path, qapp):
    src = tmp_path / "small.bmp"
    img = QImage(80, 40, QImage.Format_RGB32)
    img.fill(QColor("red"))
    img.save(str(src))
    out = QImage.fromData(load_logo_image(src))
    assert (out.width(), out.height()) == (80, 40)


def test_logo_unreadable(tmp_path, qapp):
    bad = tmp_path / "x.png"
    bad.write_bytes(b"nope")
    with pytest.raises(LogoError, match="^Couldn't read that image.$"):
        load_logo_image(bad)
    with pytest.raises(LogoError):
        load_logo_image(tmp_path / "missing.png")


def test_logo_save_read_remove(cfg_dir, qapp):
    assert read_logo() is None
    data = _jpeg()
    save_logo(data)
    assert logo_path() == cfg_dir / "logo.jpg"
    assert read_logo() == data
    remove_logo()
    assert read_logo() is None
    remove_logo()  # idempotent


def test_read_logo_corrupt(cfg_dir, qapp):
    cfg_dir.mkdir(parents=True)
    logo_path().write_bytes(b"garbage")
    assert read_logo() is None


def test_image_filter(qapp):
    f = image_filter()
    assert f.startswith("Images (") and "*.png" in f and "*.jpg" in f


def _line(desc="Plate", qty=2, unit="5.00", amt="10.00"):
    return InvoiceLine(desc, qty, Decimal(unit), Decimal(amt))


def test_html_escapes_user_text():
    html = invoice_html(
        company_name='<b>&"Acme"</b>', has_logo=False, number="INV-0001",
        date=date(2026, 10, 19), bill_to="<script>",
        lines=[InvoiceLine("a<b", 1, Decimal("1.00"), Decimal("1.00"))],
        currency_symbol="₱",
    )
    assert "<script>" not in html and "&lt;b&gt;&amp;" in html and "a&lt;b" in html
    assert "Thank you for your business!" in html and "₱1.00" in html
    assert "19 Oct 2026" in html


def test_html_date_no_leading_zero_and_negative_line_and_no_bill_to():
    html = invoice_html(
        company_name="Acme", has_logo=True, number="INV-0002",
        date=date(2026, 11, 5), bill_to="",
        lines=[_line(), InvoiceLine("Rounding", 1, Decimal("-0.01"), Decimal("-0.01"))],
        currency_symbol="₱",
    )
    assert "5 Nov 2026" in html and "05 Nov" not in html
    assert "Bill to" not in html
    assert "-₱0.01" in html and "₱9.99" in html
    assert 'src="logo"' in html


def test_render_pdf(tmp_path, qapp):
    p = tmp_path / "sub" / "inv.pdf"
    render_invoice_pdf(
        p, company_name="Acme", logo_jpeg=None, number="INV-0001",
        date=date(2026, 10, 19), bill_to="Ana", lines=[_line()], currency_symbol="₱",
    )
    assert p.read_bytes()[:4] == b"%PDF" and p.stat().st_size > 1000
    assert [x.name for x in p.parent.iterdir()] == ["inv.pdf"]


def test_render_pdf_with_logo(tmp_path, qapp):
    p = tmp_path / "inv.pdf"
    render_invoice_pdf(
        p, company_name="Acme", logo_jpeg=_jpeg(), number="INV-0001",
        date=date(2026, 10, 19), bill_to="Ana", lines=[_line()], currency_symbol="₱",
    )
    assert p.read_bytes()[:4] == b"%PDF"


def test_render_pdf_corrupt_logo_does_not_crash(tmp_path, qapp):
    p = tmp_path / "inv.pdf"
    render_invoice_pdf(
        p, company_name="Acme", logo_jpeg=b"garbage", number="INV-0001",
        date=date(2026, 10, 19), bill_to="", lines=[_line()], currency_symbol="₱",
    )
    assert p.read_bytes()[:4] == b"%PDF"


def _tool(name):
    import shutil
    path = shutil.which(name)
    if path is None:
        pytest.skip(f"{name} not available")
    return path


def _render(tmp_path, lines, logo=None):
    p = tmp_path / "inv.pdf"
    render_invoice_pdf(
        p, company_name="Acme", logo_jpeg=logo, number="INV-0001",
        date=date(2026, 10, 19), bill_to="Ana", lines=lines, currency_symbol="₱",
    )
    return p


def test_one_page_pdf_has_no_page_number_footer(tmp_path, qapp):
    import subprocess
    p = _render(tmp_path, [_line()])
    pages = subprocess.run([_tool("pdfinfo"), str(p)], capture_output=True, text=True).stdout
    assert next(x for x in pages.splitlines() if x.startswith("Pages:")).split()[1] == "1"
    text = subprocess.run([_tool("pdftotext"), "-layout", str(p), "-"],
                          capture_output=True, text=True).stdout
    assert "Thank you for your business!" in text
    lone = [ln.strip() for ln in text.splitlines() if ln.strip() in {"1", "2"}]
    assert lone == [], "stray page number"


def test_long_invoice_paginates_manually(tmp_path, qapp):
    import subprocess
    lines = [_line(f"Part {i}") for i in range(80)]
    p = _render(tmp_path, lines)
    out = subprocess.run([_tool("pdfinfo"), str(p)], capture_output=True, text=True).stdout
    n = int(next(x for x in out.splitlines() if x.startswith("Pages:")).split()[1])
    assert n >= 2
    text = subprocess.run([_tool("pdftotext"), str(p), "-"], capture_output=True, text=True).stdout
    assert "Part 0" in text and "Part 79" in text and "Thank you for your business!" in text


def test_logo_prints_at_sensible_physical_size(tmp_path, qapp):
    import subprocess
    p = _render(tmp_path, [_line()], logo=_jpeg(150, 150))
    out = subprocess.run([_tool("pdfimages"), "-list", str(p)],
                         capture_output=True, text=True).stdout.splitlines()
    row = out[2].split()  # page num type width height color comp bpc enc interp object ID x-ppi y-ppi
    assert (row[3], row[4]) == ("150", "150")
    mm = 150 / float(row[12]) * 25.4
    assert 35 <= mm <= 40, mm
