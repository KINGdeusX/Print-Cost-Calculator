"""One plate: thumbnail, name, print time, copies, filaments, labor."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame, QSizePolicy, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QToolButton, QVBoxLayout, QWidget,
)

from pcc.core.models import FilamentUse
from pcc.gui.icons import icon
from pcc.gui.widgets.job_panel import caption
from pcc.gui.widgets.money_spin import (
    GuardedCombo, GuardedDoubleSpin, GuardedSpin, MoneySpin, no_drops,
)

THUMB = 64
_BADGE_MATCHES = ("type", "default")


def swatch(color: str) -> QPixmap:
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(QColor(0, 0, 0, 90))
    p.drawEllipse(1, 1, 14, 14)
    p.end()
    return pm


class _ClickLabel(QLabel):
    def mousePressEvent(self, event) -> None:
        self.on_click()

    def on_click(self) -> None:  # replaced by the row
        pass


class FilamentRow(QWidget):
    def __init__(self, card: "PlateCard"):
        super().__init__()
        self.card = card
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.combo = GuardedCombo()
        self.combo.setToolTip("Which of your filaments is used")
        self.combo.setMinimumWidth(120)
        self.grams_spin = GuardedDoubleSpin()
        self.grams_spin.setRange(0, 1e6)
        self.grams_spin.setDecimals(1)
        self.grams_spin.setSuffix(" g")
        self.grams_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.grams_spin.setToolTip("Filament weight used per copy, from your slicer")
        self.badge = _ClickLabel("🟡")
        self.badge.on_click = self.combo.showPopup
        self.remove_button = QToolButton()
        self.remove_button.setIcon(icon("trash", size=16))
        self.remove_button.setToolTip("Remove this filament")
        row.addWidget(self.combo, 1)
        row.addWidget(self.grams_spin)
        row.addWidget(self.badge)
        row.addWidget(self.remove_button)
        self._items: list[tuple] = []
        self.combo.activated.connect(self._on_combo)
        self.grams_spin.valueChanged.connect(self._on_grams)
        self.remove_button.clicked.connect(self._on_remove)

    @property
    def index(self) -> int:
        return self.card.rows.index(self)

    def set_catalog(self, catalog) -> None:
        items = [(f.id, f.name, f.color) for f in catalog.filaments]
        if items == self._items:
            return
        self._items = items
        self.combo.blockSignals(True)
        self.combo.clear()
        for fid, name, color in items:
            self.combo.addItem(QIcon(swatch(color)), name, fid)
        self.combo.blockSignals(False)

    def set_use(self, use: FilamentUse, removable: bool) -> None:
        i = self.combo.findData(use.filament_id)
        if i >= 0 and i != self.combo.currentIndex():
            self.combo.blockSignals(True)
            self.combo.setCurrentIndex(i)
            self.combo.blockSignals(False)
        if abs(self.grams_spin.value() - use.grams) > 1e-9:
            self.grams_spin.blockSignals(True)
            self.grams_spin.setValue(use.grams)
            self.grams_spin.blockSignals(False)
        show = use.match in _BADGE_MATCHES
        self.badge.setVisible(show)
        if show:
            src = " ".join(x for x in (use.source_name or use.source_type,) if x)
            self.badge.setToolTip(
                f"Closest match{' for ' + src if src else ''}. "
                "Click to pick the right filament.")
        self.remove_button.setVisible(removable)

    def _on_combo(self, i: int) -> None:
        fid = self.combo.itemData(i)
        self.card.edit_use(self.index, filament_id=fid, match="manual")

    def _on_grams(self, v: float) -> None:
        self.card.edit_use(self.index, grams=v)

    def _on_remove(self) -> None:
        self.card.remove_use(self.index)


class PlateCard(QFrame):
    def __init__(self, state, plate_id: str, parent=None):
        super().__init__(parent)
        self.state = state
        self.plate_id = plate_id
        self.rows: list[FilamentRow] = []
        self.setProperty("card", True)
        # never let the scroll area squeeze a card below its natural height
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        col = QVBoxLayout(self)
        col.setContentsMargins(16, 14, 16, 14)
        col.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(12)
        self.thumb = QLabel()
        self.thumb.setFixedSize(THUMB, THUMB)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setToolTip("Preview from the sliced file")
        self.name_edit = QLineEdit()
        self.name_edit.setToolTip("A name for this plate")
        self.name_edit.setPlaceholderText("Plate name")
        no_drops(self.name_edit)
        self.remove_button = QToolButton()
        self.remove_button.setIcon(icon("trash"))
        self.remove_button.setToolTip("Remove this plate")
        top.addWidget(self.thumb)
        top.addWidget(self.name_edit, 1)
        top.addWidget(self.remove_button, 0, Qt.AlignmentFlag.AlignTop)
        col.addLayout(top)

        tip_time = "Print time per copy, from your slicer"
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(2)
        self.days_spin = GuardedSpin()
        self.days_spin.setRange(0, 999)
        self.days_spin.setSuffix(" d")
        self.hours_spin = GuardedSpin()
        self.hours_spin.setRange(0, 23)
        self.hours_spin.setSuffix(" h")
        self.minutes_spin = GuardedSpin()
        self.minutes_spin.setRange(0, 59)
        self.minutes_spin.setSuffix(" min")
        self.copies_spin = GuardedSpin()
        self.copies_spin.setRange(1, 999)
        self.copies_spin.setPrefix("× ")
        tip_copies = "How many times this plate is printed"
        for spin in (self.days_spin, self.hours_spin, self.minutes_spin):
            spin.setToolTip(tip_time)
            spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.copies_spin.setToolTip(tip_copies)
        grid.addWidget(caption("⏱ Print time per copy", tip_time), 0, 0, 1, 3)
        grid.addWidget(caption("🔁 Copies", tip_copies), 0, 3)
        for i, spin in enumerate((self.days_spin, self.hours_spin, self.minutes_spin,
                                  self.copies_spin)):
            grid.addWidget(spin, 1, i)
            grid.setColumnStretch(i, 1)
        col.addLayout(grid)

        col.addWidget(caption("🧵 Filament", "Filament used per copy, one row per color"))
        self.rows_box = QVBoxLayout()
        self.rows_box.setSpacing(6)
        col.addLayout(self.rows_box)
        self.add_filament_button = QPushButton("➕ Filament")
        self.add_filament_button.setToolTip("Add another filament used on this plate")
        col.addWidget(self.add_filament_button, 0, Qt.AlignmentFlag.AlignLeft)

        tip = "Your time per plate: removal, cleanup, post-processing"
        col.addWidget(caption("🛠 Labor (per plate)", tip))
        self.labor_spin = MoneySpin(state.settings.currency_symbol)
        self.labor_spin.setToolTip(tip)
        col.addWidget(self.labor_spin)

        self._thumb_bytes: bytes | None = b"\0"  # force first paint
        self.refresh()

        self.name_edit.textEdited.connect(lambda t: self._set(name=t))
        for s in (self.days_spin, self.hours_spin, self.minutes_spin):
            s.valueChanged.connect(self._on_time)
        self.copies_spin.valueChanged.connect(lambda v: self._set(copies=v))
        self.labor_spin.valueChanged.connect(lambda v: self._set(labor=v))
        self.add_filament_button.clicked.connect(self._add_use)
        self.remove_button.clicked.connect(
            lambda: self.state.remove_plate(self.plate_id))

    # -- model access ---------------------------------------------------
    @property
    def plate(self):
        return next((p for p in self.state.job.plates if p.id == self.plate_id), None)

    def _set(self, **fields) -> None:
        self.state.update_plate(self.plate_id, **fields)

    def _on_time(self) -> None:
        hours = (self.days_spin.value() * 24 + self.hours_spin.value()
                 + self.minutes_spin.value() / 60)
        self._set(hours=hours)

    def edit_use(self, index: int, **changes) -> None:
        uses = list(self.plate.filaments)
        uses[index] = replace(uses[index], **changes)
        self._set(filaments=uses)

    def remove_use(self, index: int) -> None:
        uses = list(self.plate.filaments)
        if len(uses) > 1:
            del uses[index]
            self._set(filaments=uses)

    def _add_use(self) -> None:
        uses = list(self.plate.filaments)
        uses.append(FilamentUse(self.state.catalog.default_filament().id, 0.0))
        self._set(filaments=uses)

    # -- sync -----------------------------------------------------------
    def refresh(self) -> None:
        plate = self.plate
        if plate is None:
            return
        if self.name_edit.text() != plate.name:
            self.name_edit.setText(plate.name)
        mins = round(plate.hours * 60)
        cur = (self.days_spin.value() * 24 + self.hours_spin.value()) * 60 \
            + self.minutes_spin.value()
        if cur != mins:
            d, rem = divmod(mins, 1440)
            h, m = divmod(rem, 60)
            for spin, v in ((self.days_spin, d), (self.hours_spin, h),
                            (self.minutes_spin, m)):
                spin.blockSignals(True)
                spin.setValue(v)
                spin.blockSignals(False)
        if self.copies_spin.value() != plate.copies:
            self.copies_spin.blockSignals(True)
            self.copies_spin.setValue(plate.copies)
            self.copies_spin.blockSignals(False)
        self.labor_spin.set_symbol(self.state.settings.currency_symbol)
        if abs(self.labor_spin.value() - plate.labor) > 1e-9:
            self.labor_spin.blockSignals(True)
            self.labor_spin.setValue(plate.labor)
            self.labor_spin.blockSignals(False)
        while len(self.rows) < len(plate.filaments):
            r = FilamentRow(self)
            self.rows.append(r)
            self.rows_box.addWidget(r)
        while len(self.rows) > len(plate.filaments):
            r = self.rows.pop()
            self.rows_box.removeWidget(r)
            r.deleteLater()
        for r, use in zip(self.rows, plate.filaments):
            r.set_catalog(self.state.catalog)
            r.set_use(use, removable=len(plate.filaments) > 1)
        self._refresh_thumb(plate.thumbnail_png)
        # style-sheet min-heights only count once polished; measure after that
        for w in self.findChildren(QWidget):
            w.ensurePolished()
        self.layout().invalidate()
        self.updateGeometry()

    def _refresh_thumb(self, png: bytes | None) -> None:
        if png == self._thumb_bytes:
            return
        self._thumb_bytes = png
        pm = QPixmap()
        if png and pm.loadFromData(png):
            self.thumb.setPixmap(pm.scaled(
                THUMB, THUMB, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        else:
            self.thumb.setPixmap(icon("printer", size=32).pixmap(32, 32))
