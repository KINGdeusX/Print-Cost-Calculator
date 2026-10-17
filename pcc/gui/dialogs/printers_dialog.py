"""Manage printer profiles."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QPlainTextEdit, QLineEdit

from pcc.core.models import PrinterProfile, new_id
from pcc.gui.dialogs._catalog_dialog import CatalogDialog, muted
from pcc.gui.widgets.money_spin import GuardedDoubleSpin, no_drops

MATCH_HINT = "Used to auto-select this printer when importing a .3mf (e.g. P1S, X1C)"


def parse_matches(text: str) -> list[str]:
    return [p.strip() for p in text.split(",") if p.strip()]


class PrintersDialog(CatalogDialog):
    title = "Manage printers"
    noun = "printer"

    def items(self):
        return self.catalog.printers

    def build_form(self) -> None:
        self.watts_spin = GuardedDoubleSpin()
        self.watts_spin.setRange(1, 5000)
        self.watts_spin.setDecimals(0)
        self.watts_spin.setSuffix(" W")
        self.watts_spin.setToolTip("Average power the printer draws while printing")
        self.match_edit = QLineEdit()
        self.match_edit.setToolTip(MATCH_HINT)
        no_drops(self.match_edit)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setToolTip("Anything you want to remember about this printer")
        self.notes_edit.setFixedHeight(80)
        self.form.addRow("Power", self.watts_spin)
        self.form.addRow("Model match", self.match_edit)
        self.form.addRow(muted(MATCH_HINT))
        self.form.addRow("Notes", self.notes_edit)
        self.watts_spin.valueChanged.connect(lambda v: self._set(watts=float(v)))
        self.match_edit.textEdited.connect(
            lambda t: self._set(model_match=parse_matches(t)))
        self.notes_edit.textChanged.connect(
            lambda: self._set(notes=self.notes_edit.toPlainText()))

    def _set(self, **fields) -> None:
        it = self.current_item()
        if it is not None and not self._loading:
            for k, v in fields.items():
                setattr(it, k, v)

    def load_form(self, p) -> None:
        self.watts_spin.setValue(p.watts)
        self.match_edit.setText(", ".join(p.model_match))
        self.notes_edit.setPlainText(p.notes)

    def new_item(self):
        return PrinterProfile(id=new_id("printer"), name="New printer", watts=150.0)

    def clone_item(self, p):
        return replace(p, id=new_id("printer"), name=f"{p.name} (copy)",
                       model_match=list(p.model_match))

    def can_delete(self, p) -> bool:
        return self.catalog.can_delete_printer(p.id)
