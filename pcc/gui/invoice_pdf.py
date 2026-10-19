"""Invoice HTML and PDF rendering (QTextDocument -> QPdfWriter)."""
from __future__ import annotations

import datetime
import os
import tempfile
from decimal import Decimal
from html import escape
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, QUrl
from PySide6.QtGui import (
    QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument,
)

from pcc.core.currency import format_money
from pcc.core.invoice import InvoiceLine, invoice_total

ACCENT = "#F26B1D"
_MUTED = "#777777"
_RULE = "#DDDDDD"
_DPI = 300
_CSS_DPI = 96
_LOGO_MM_PER_PX = 0.25  # a 150 px logo prints ~37.5 mm wide


def _money(amount: Decimal, symbol: str) -> str:
    return escape(format_money(float(amount), symbol))


def _fmt_date(d: datetime.date) -> str:
    return f"{d.day} {d:%b %Y}"


def invoice_html(
    *,
    company_name: str,
    has_logo: bool,
    number: str,
    date: datetime.date,
    bill_to: str,
    lines: list[InvoiceLine],
    currency_symbol: str,
) -> str:
    logo = '<img src="logo"><br>' if has_logo else ""
    name = (
        f'<span style="font-size:16pt; font-weight:bold;">{escape(company_name)}</span>'
        if company_name
        else ""
    )
    bill = ""
    if bill_to.strip():
        body = "<br>".join(escape(ln) for ln in bill_to.strip().splitlines())
        bill = (
            f'<p style="margin-top:22px; margin-bottom:0;"><span style="color:{_MUTED}; '
            f'font-size:9pt;">Bill to:</span><br>{body}</p>'
        )
    cell = f'style="border-bottom:1px solid {_RULE};"'
    rows = []
    for i, ln in enumerate(lines, 1):
        rows.append(
            f"<tr><td {cell}>{i}</td><td {cell}>{escape(ln.description)}</td>"
            f'<td {cell} align="right">{ln.qty}</td>'
            f'<td {cell} align="right">{_money(ln.unit_price, currency_symbol)}</td>'
            f'<td {cell} align="right">{_money(ln.amount, currency_symbol)}</td></tr>'
        )
    total = _money(invoice_total(lines), currency_symbol)
    top = "border-top:2px solid #333333;"
    head = (
        '<tr bgcolor="#F2F2F2"><th align="left">#</th><th align="left">Description</th>'
        '<th align="right">Qty</th><th align="right">Unit price</th>'
        '<th align="right">Amount</th></tr>'
    )
    return (
        '<html><body style="font-family:Helvetica, Arial, sans-serif; font-size:10pt; '
        'color:#222222;">'
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        f'<td width="55%" valign="top">{logo}{name}</td>'
        '<td width="45%" valign="top" align="right">'
        f'<span style="font-size:28pt; font-weight:bold; color:{ACCENT};">INVOICE</span><br>'
        f'<span style="color:{_MUTED};">No.</span> {escape(number)}<br>'
        f'<span style="color:{_MUTED};">Date</span> {_fmt_date(date)}'
        "</td></tr></table>"
        f"{bill}"
        '<p style="margin:0;">&nbsp;</p>'
        '<table width="100%" cellspacing="0" cellpadding="6">'
        f"{head}{''.join(rows)}"
        f'<tr><td style="{top}"></td><td style="{top}"></td><td style="{top}"></td>'
        f'<td style="{top}" align="right"><b>TOTAL</b></td>'
        f'<td style="{top}" align="right"><b>{total}</b></td></tr>'
        "</table>"
        f'<p align="center" style="margin-top:40px; color:{_MUTED};">'
        "Thank you for your business!</p>"
        "</body></html>"
    )


def _paginate(doc: QTextDocument, writer: QPdfWriter) -> None:
    """Paint the document page by page (QTextDocument.print_ adds a page number)."""
    area = writer.pageLayout().paintRectPixels(writer.resolution())
    page_w, page_h = float(area.width()), float(area.height())
    doc.setPageSize(QSizeF(page_w, page_h))
    pages = max(1, int(doc.pageCount()))
    painter = QPainter(writer)
    try:
        for i in range(pages):
            if i:
                writer.newPage()
            painter.save()
            painter.translate(0, -i * page_h)
            doc.drawContents(painter, QRectF(0, i * page_h, page_w, page_h))
            painter.restore()
    finally:
        painter.end()


def render_invoice_pdf(
    path: Path,
    *,
    company_name: str,
    logo_jpeg: bytes | None,
    number: str,
    date: datetime.date,
    bill_to: str,
    lines: list[InvoiceLine],
    currency_symbol: str,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logo = QImage.fromData(logo_jpeg) if logo_jpeg else QImage()
    has_logo = not logo.isNull()
    html = invoice_html(
        company_name=company_name, has_logo=has_logo, number=number, date=date,
        bill_to=bill_to, lines=lines, currency_symbol=currency_symbol,
    )
    if has_logo:
        px_per_mm = _CSS_DPI / 25.4  # Qt scales <img> sizes from 96 dpi CSS px to the device
        w = round(logo.width() * _LOGO_MM_PER_PX * px_per_mm)
        h = round(logo.height() * _LOGO_MM_PER_PX * px_per_mm)
        html = html.replace('<img src="logo">', f'<img src="logo" width="{w}" height="{h}">', 1)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    os.close(fd)
    try:
        writer = QPdfWriter(tmp_name)
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Millimeter)
        writer.setResolution(_DPI)
        doc = QTextDocument()
        if has_logo:
            doc.addResource(QTextDocument.ImageResource, QUrl("logo"), logo)
        doc.documentLayout().setPaintDevice(writer)
        doc.setHtml(html)
        _paginate(doc, writer)
        del writer  # flush and close the file
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
