"""Create an invoice PDF for the open project and record it in the project."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout,
)

from pcc.core.invoice import build_invoice_lines, invoice_total
from pcc.core.models import Settings
from pcc.core.paths import invoices_dir
from pcc.core.projects import InvoiceRecord, ProjectConflictError, ProjectError, safe_name
from pcc.gui.invoice_pdf import render_invoice_pdf
from pcc.gui.logo import read_logo

_NUMBER = re.compile(r"INV-(\d+)")


def default_invoice_number(settings: Settings) -> str:
    return f"INV-{settings.next_invoice_number:04d}"


def invoice_file_path(number: str, bill_to: str, project_name: str) -> Path:
    return invoices_dir() / f"{number} - {safe_name(bill_to or project_name)}.pdf"


def invoice_exists(number: str) -> bool:
    d = invoices_dir()
    return any(
        p.name == f"{number}.pdf" or p.name.startswith(f"{number} ")
        for p in d.glob("*.pdf")
    )


class InvoiceDialog(QDialog):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle("🧾 Invoice")
        self.setMinimumWidth(380)
        self.created_path: Path | None = None
        self.number_edit = QLineEdit(default_invoice_number(state.settings))
        self.number_edit.setToolTip("Invoice number")
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("d MMM yyyy")
        self.bill_to_edit = QLineEdit(state.job.customer)
        self.bill_to_edit.setPlaceholderText("Customer name (optional)")
        form = QFormLayout()
        form.addRow("Invoice no.", self.number_edit)
        form.addRow("Date", self.date_edit)
        form.addRow("Bill to", self.bill_to_edit)
        self.create_button = QPushButton("🧾 Create PDF")
        self.create_button.setProperty("accent", True)
        self.create_button.setDefault(True)
        cancel = QPushButton("Cancel")
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(self.create_button)
        col = QVBoxLayout(self)
        col.addLayout(form)
        col.addLayout(row)
        cancel.clicked.connect(self.reject)
        self.create_button.clicked.connect(self._on_create)
        self.number_edit.textChanged.connect(
            lambda t: self.create_button.setEnabled(bool(t.strip())))

    def _on_create(self) -> None:
        if self.issue() is not None:
            self.accept()

    # -- the flow -------------------------------------------------------
    def issue(self) -> Path | None:
        state = self.state
        number = self.number_edit.text().strip()
        if not number or state.quote is None or state.project is None:
            return None
        bill_to = self.bill_to_edit.text().strip()
        path = invoice_file_path(number, bill_to, state.project.name)
        # One prompt covers a reused number and an existing file of that name.
        if invoice_exists(number) and QMessageBox.question(
                self, "Invoice exists", f"Invoice {number} already exists. Create anyway?",
        ) != QMessageBox.StandardButton.Yes:
            return None
        lines = build_invoice_lines(state.quote)
        date = self.date_edit.date().toPython()
        if not self._render(path, number, date, bill_to, lines):
            return None
        record = InvoiceRecord(
            number=number, date=date.isoformat(), bill_to=bill_to,
            total=float(invoice_total(lines)),
            currency_symbol=state.settings.currency_symbol, file=str(path))
        if not self._record(record):
            return None
        m = _NUMBER.fullmatch(number)
        if m and int(m.group(1)) >= state.settings.next_invoice_number:
            state.update_settings(next_invoice_number=int(m.group(1)) + 1)
        self.created_path = path
        return path

    def _render(self, path, number, date, bill_to, lines) -> bool:
        while True:
            try:
                render_invoice_pdf(
                    path, company_name=self.state.settings.company_name,
                    logo_jpeg=read_logo(), number=number, date=date, bill_to=bill_to,
                    lines=lines, currency_symbol=self.state.settings.currency_symbol)
                return True
            except PermissionError:
                box = QMessageBox(
                    QMessageBox.Icon.Warning, "File is open",
                    "Close the file in your PDF viewer, then retry",
                    QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel,
                    self)
                if box.exec() != QMessageBox.StandardButton.Retry:
                    return False
            except OSError as e:
                QMessageBox.critical(self, "Couldn't create invoice",
                                     f"Couldn't write the PDF: {e.strerror or e}")
                return False

    def _record(self, record: InvoiceRecord) -> bool:
        state = self.state
        try:
            try:
                state.record_invoice(record)
            except ProjectConflictError:
                window = self.parent()
                confirm = getattr(window, "confirm_overwrite", None)
                if confirm is None or not confirm():
                    return False
                state.save_project(force=True)
            return True
        except (OSError, ProjectError) as e:
            QMessageBox.critical(self, "Couldn't save",
                                 f"Couldn't save the invoice record: {getattr(e, 'strerror', None) or e}")
            return False
