import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from PySide6.QtCore import QDate
from PySide6.QtGui import QColor, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QMessageBox, QPushButton

from pcc.core.invoice import build_invoice_lines, invoice_total
from pcc.core.paths import invoices_dir
from pcc.core.projects import ProjectConflictError
from pcc.gui.dialogs import invoice_dialog as idlg
from pcc.gui.dialogs.invoice_dialog import (
    InvoiceDialog, default_invoice_number, invoice_exists, invoice_file_path,
)
from pcc.gui.dialogs.settings_dialog import SettingsDialog
from pcc.gui.invoice_pdf import invoice_html
from pcc.gui.main_window import MainWindow
from pcc.gui.state import AppState

Yes = QMessageBox.StandardButton.Yes
No = QMessageBox.StandardButton.No


def make(qtbot, company="Acme 3D", customer="Ana", plate=True):
    state = AppState(legacy_paths=[])
    state.new_project()
    if company:
        state.update_settings(company_name=company)
    if plate:
        state.add_plate()
        state.update_plate(state.job.plates[0].id, hours=1.0)
    state.update_job(customer=customer)
    state.save_project()
    w = MainWindow(state)
    qtbot.addWidget(w)
    w.show_editor()
    return state, w


def dialog(qtbot, w):
    d = InvoiceDialog(w.state, w)
    qtbot.addWidget(d)
    return d


def test_helpers(cfg_dir, data_dir):
    from pcc.core.models import Settings
    assert default_invoice_number(Settings(next_invoice_number=7)) == "INV-0007"
    p = invoice_file_path("INV-0001", "Ana", "Proj")
    assert p == invoices_dir() / "INV-0001 - Ana.pdf"
    assert invoice_file_path("INV-0001", "", "My proj").name == "INV-0001 - My proj.pdf"
    assert not invoice_exists("INV-0001")
    (invoices_dir() / "INV-0001 - Ana.pdf").write_bytes(b"x")
    (invoices_dir() / "INV-0002.pdf").write_bytes(b"x")
    assert invoice_exists("INV-0001") and invoice_exists("INV-0002")
    assert not invoice_exists("INV-000") and not invoice_exists("INV-0003")


def test_first_invoice_prompts_for_company(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot, company="")
    seen = []

    def fake_exec(self):
        seen.append(self.company_edit.text())
        self.company_edit.setText("Acme 3D")
        self.accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(SettingsDialog, "exec", fake_exec)
    shown = []
    monkeypatch.setattr(InvoiceDialog, "exec", lambda self: shown.append(self) or 0)
    w.open_invoice_dialog()
    assert seen == [""] and state.settings.company_name == "Acme 3D"
    assert len(shown) == 1


def test_company_prompt_cancelled_or_blank_aborts(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot, company="")
    shown = []
    monkeypatch.setattr(InvoiceDialog, "exec", lambda self: shown.append(1) or 0)
    monkeypatch.setattr(SettingsDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    w.open_invoice_dialog()
    monkeypatch.setattr(SettingsDialog, "exec",
                        lambda self: QDialog.DialogCode.Accepted)  # accepted but still blank
    w.open_invoice_dialog()
    assert shown == []


def test_issue_creates_pdf_records_and_advances(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    d = dialog(qtbot, w)
    assert d.number_edit.text() == "INV-0001" and d.bill_to_edit.text() == "Ana"
    assert d.date_edit.date() == QDate.currentDate() and d.date_edit.calendarPopup()
    path = d.issue()
    assert path == invoices_dir() / "INV-0001 - Ana.pdf"
    assert path.read_bytes()[:4] == b"%PDF"
    rec = state.project.invoices[-1]
    assert rec.number == "INV-0001" and rec.bill_to == "Ana" and rec.file == str(path)
    assert rec.date == date.today().isoformat()
    assert rec.total == pytest.approx(float(state.quote.price))
    assert state.settings.next_invoice_number == 2
    assert not state.dirty
    # the record really reached disk
    from pcc.core.projects import load_project
    assert load_project(state.project_path).invoices[-1].number == "INV-0001"


def test_custom_higher_number_advances(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    d = dialog(qtbot, w)
    d.number_edit.setText("INV-0042")
    assert d.issue() is not None
    assert state.settings.next_invoice_number == 43
    d.number_edit.setText("Q-7")
    assert d.issue() is not None
    assert state.settings.next_invoice_number == 43
    d.number_edit.setText("INV-0005")  # lower than next: unchanged
    assert d.issue() is not None
    assert state.settings.next_invoice_number == 43


def test_duplicate_number_warns(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    existing = invoices_dir() / "INV-0001 - Old.pdf"
    existing.write_bytes(b"old")
    asked = []

    def ask(parent, title, text, *a, **k):
        asked.append(text)
        return No

    monkeypatch.setattr(QMessageBox, "question", ask)
    d = dialog(qtbot, w)
    assert d.issue() is None
    assert asked == ["Invoice INV-0001 already exists. Create anyway?"]
    assert [p.name for p in invoices_dir().glob("*.pdf")] == [existing.name]
    assert state.project.invoices == [] and state.settings.next_invoice_number == 1
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: Yes)
    assert d.issue() is not None
    assert state.settings.next_invoice_number == 2


def test_filename_sanitized(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    d = dialog(qtbot, w)
    d.bill_to_edit.setText('A/B:"C"')
    path = d.issue()
    assert path is not None and path.exists()
    assert not set('/:"') & set(path.name)


def test_missing_logo_still_renders(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "logo.jpg").write_bytes(b"corrupt")
    path = dialog(qtbot, w).issue()
    assert path is not None and path.read_bytes()[:4] == b"%PDF"


def test_invoice_button_enablement(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot, plate=False)
    assert w.summary.invoice_button.text() == "🧾 Invoice"
    assert not w.summary.invoice_button.isEnabled()  # empty job
    state.add_plate()
    state.update_plate(state.job.plates[0].id, hours=1.0)
    assert w.summary.invoice_button.isEnabled()
    state.save_project()
    state.close_project()
    assert not w.summary.invoice_button.isEnabled()  # list page / no project


def test_invoice_lines_hide_internal(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    state.update_settings(hidden_plate_fee=30.0, margin_pct=50.0)
    q = state.quote
    lines = build_invoice_lines(q)
    html = invoice_html(company_name="Acme", has_logo=False, number="INV-0001",
                        date=date(2026, 10, 19), bill_to="Ana", lines=lines,
                        currency_symbol="₱")
    from PySide6.QtGui import QTextDocument
    doc = QTextDocument()
    doc.setHtml(html)
    low = doc.toPlainText().lower()  # visible text only (CSS has 'margin')
    assert "fee" not in low and "margin" not in low and "cost" not in low
    assert invoice_total(lines) == Decimal(str(q.price)).quantize(Decimal("0.01"))


def test_permission_error_retry_then_success(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    real, calls = idlg.render_invoice_pdf, []

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError
        return real(*a, **k)

    boxes = []

    def fake_exec(self):
        boxes.append(self.text())
        return QMessageBox.StandardButton.Retry

    monkeypatch.setattr(idlg, "render_invoice_pdf", flaky)
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    assert dialog(qtbot, w).issue() is not None
    assert len(calls) == 3
    assert boxes == ["Close the file in your PDF viewer, then retry"] * 2


def test_permission_error_cancel_leaves_everything(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    monkeypatch.setattr(idlg, "render_invoice_pdf",
                        lambda *a, **k: (_ for _ in ()).throw(PermissionError()))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Cancel)
    assert dialog(qtbot, w).issue() is None
    assert state.project.invoices == [] and state.settings.next_invoice_number == 1


def test_conflict_overwrite_forces_save(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    forced = []
    real = state.save_project

    def save(force=False):
        if not force:
            raise ProjectConflictError("changed")
        forced.append(1)
        real(force=True)

    monkeypatch.setattr(state, "save_project", save)
    monkeypatch.setattr(w, "confirm_overwrite", lambda: True)
    assert dialog(qtbot, w).issue() is not None
    assert forced == [1] and state.settings.next_invoice_number == 2
    assert not state.dirty


def test_conflict_cancel_does_not_advance(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)

    def save(force=False):
        raise ProjectConflictError("changed")

    monkeypatch.setattr(state, "save_project", save)
    monkeypatch.setattr(w, "confirm_overwrite", lambda: False)
    assert dialog(qtbot, w).issue() is None
    assert state.settings.next_invoice_number == 1


def test_save_failure_does_not_advance(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    monkeypatch.setattr(state, "save_project",
                        lambda force=False: (_ for _ in ()).throw(OSError(28, "No space")))
    crit = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: crit.append(a[2]))
    assert dialog(qtbot, w).issue() is None
    assert crit and state.settings.next_invoice_number == 1


def test_full_flow_toast_and_actions(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    opened = []
    monkeypatch.setattr("pcc.gui.main_window.QDesktopServices.openUrl",
                        lambda url: opened.append(Path(url.toLocalFile())))

    def run(self):
        if self.issue() is None:
            return 0
        self.accept()
        return 1

    monkeypatch.setattr(InvoiceDialog, "exec", run)
    w.summary.invoice_button.click()
    assert w.toast.label.text() == "🧾 Saved INV-0001"
    btns = {b.text(): b for b in w.toast.findChildren(QPushButton)}
    p = invoices_dir() / "INV-0001 - Ana.pdf"
    btns["Open"].click()
    assert opened == [p]


def test_ctrl_i_opens_only_in_editor(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    calls = []
    monkeypatch.setattr(MainWindow, "open_invoice_dialog", lambda self: calls.append(1))
    w._ctrl_i()
    assert calls == [1]
    state.save_project()
    state.close_project()
    w._ctrl_i()
    assert calls == [1]
    sc = [s for s in w.findChildren(QShortcut) if s.key() == QKeySequence("Ctrl+I")]
    assert len(sc) == 1


def test_visual_sample(qtbot, cfg_dir, data_dir, monkeypatch, tmp_path):
    import os
    out = os.environ.get("PCC_T8_OUT")
    if not out:
        pytest.skip("manual visual check")
    img = QImage(150, 150, QImage.Format_RGB32)
    img.fill(QColor("#336699"))
    cfg_dir.mkdir(parents=True, exist_ok=True)
    img.save(str(cfg_dir / "logo.jpg"), "JPEG")
    state, w = make(qtbot)
    path = dialog(qtbot, w).issue()
    subprocess.run(["pdftoppm", "-png", "-r", "70", "-f", "1", "-l", "1", "-singlefile",
                    str(path), out], check=True)


def test_retry_after_failed_save_keeps_one_record(qtbot, cfg_dir, data_dir, monkeypatch):
    from pcc.core.projects import load_project
    state, w = make(qtbot)
    real = state.save_project
    fail = [True]

    def save(force=False):
        if fail.pop() if fail else False:
            raise OSError(28, "No space")
        real(force=force)

    monkeypatch.setattr(state, "save_project", save)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: Yes)
    d = dialog(qtbot, w)
    assert d.issue() is None
    assert d.issue() is not None
    assert len(state.project.invoices) == 1
    assert len(load_project(state.project_path).invoices) == 1


@pytest.mark.parametrize("number", ["a/b", "../x", 'Q:1*"?'])
def test_number_sanitized_in_filename(qtbot, cfg_dir, data_dir, number):
    state, w = make(qtbot)
    d = dialog(qtbot, w)
    d.number_edit.setText(number)
    path = d.issue()
    assert path is not None and path.parent == invoices_dir() and path.exists()
    assert not set('/\\:*?"') & set(path.name)
    assert state.project.invoices[-1].number == number
    assert invoice_exists(number)
