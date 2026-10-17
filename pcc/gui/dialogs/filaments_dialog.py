"""Manage the filament catalog."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QColorDialog, QLineEdit, QPushButton

from pcc.core.models import Filament, new_id
from pcc.gui.dialogs._catalog_dialog import CatalogDialog
from pcc.gui.widgets.money_spin import MoneySpin, no_drops
from pcc.gui.widgets.plate_card import swatch


class FilamentsDialog(CatalogDialog):
    title = "Manage filaments"
    noun = "filament"

    def items(self):
        return self.catalog.filaments

    def build_form(self) -> None:
        self.type_edit = QLineEdit()
        self.type_edit.setToolTip("Material, for example PLA, PETG or ABS")
        no_drops(self.type_edit)
        self.price_spin = MoneySpin(self.state.settings.currency_symbol)
        self.price_spin.setRange(0, 1e6)
        self.price_spin.setSuffix(" /kg")
        self.price_spin.setToolTip("What you pay for one kilogram of this filament")
        self.color_button = QPushButton()
        self.color_button.setToolTip("Pick the filament's color")
        self.set_default_button = QPushButton("★ Set as default")
        self.set_default_button.setToolTip(
            "Use this filament for new plates and as the fallback for deleted ones")
        self.form.addRow("Type", self.type_edit)
        self.form.addRow("Price", self.price_spin)
        self.form.addRow("Color", self.color_button)
        self.form.addRow(self.set_default_button)
        self.type_edit.textEdited.connect(lambda t: self._set(type=t.strip()))
        self.price_spin.valueChanged.connect(lambda v: self._set(price_per_kg=float(v)))
        self.color_button.clicked.connect(self._pick_color)
        self.set_default_button.clicked.connect(self._set_default)

    def _set(self, **fields) -> None:
        it = self.current_item()
        if it is not None and not self._loading:
            for k, v in fields.items():
                setattr(it, k, v)
            self.refresh_row()

    def decorate(self, row, f) -> None:
        row.setText((f.name or "(unnamed)") + ("  ★ default" if f.is_default else ""))
        row.setIcon(QIcon(swatch(f.color)))

    def load_form(self, f) -> None:
        self.type_edit.setText(f.type)
        self.price_spin.setValue(f.price_per_kg)
        self._show_color(f.color)
        self.set_default_button.setEnabled(not f.is_default)

    def _show_color(self, color: str) -> None:
        self.color_button.setIcon(QIcon(swatch(color)))
        self.color_button.setText(color.upper())

    def set_color(self, color: str) -> None:
        self._set(color=color)
        self._show_color(color)

    def _pick_color(self) -> None:
        f = self.current_item()
        if f is None:
            return
        c = QColorDialog.getColor(QColor(f.color), self, "Filament color")
        if c.isValid():
            self.set_color(c.name())

    def _set_default(self) -> None:
        f = self.current_item()
        if f is not None:
            self.catalog.set_default_filament(f.id)
            self._rebuild_list(self.list.currentRow())

    def new_item(self):
        return Filament(id=new_id("filament"), name="New filament", type="PLA",
                        price_per_kg=800.0, color="#808080")

    def clone_item(self, f):
        return replace(f, id=new_id("filament"), name=f"{f.name} (copy)", is_default=False)

    def can_delete(self, f) -> bool:
        return self.catalog.can_delete_filament(f.id)

    def after_delete(self, f) -> None:
        if f.is_default and self.catalog.filaments:
            self.catalog.set_default_filament(self.catalog.filaments[0].id)
