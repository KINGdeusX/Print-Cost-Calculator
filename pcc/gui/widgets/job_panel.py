"""Job-level inputs: customer, packaging, margin, failure allowance."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QSlider, QVBoxLayout,
)

from pcc.gui.widgets.money_spin import GuardedDoubleSpin, MoneySpin, no_drops


def caption(text: str, tip: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("muted", True)
    lab.setToolTip(tip)
    return lab


class JobPanel(QFrame):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setProperty("card", True)
        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(6)
        head = QLabel("👤 Job")
        f = head.font()
        f.setBold(True)
        head.setFont(f)
        col.addWidget(head)
        col.addSpacing(6)

        tip = "Who this order is for (shown in the Excel report)"
        col.addWidget(caption("👤 Customer / project", tip))
        self.customer_edit = QLineEdit()
        self.customer_edit.setPlaceholderText("Optional")
        self.customer_edit.setToolTip(tip)
        no_drops(self.customer_edit)
        col.addWidget(self.customer_edit)
        col.addSpacing(8)

        tip = "Charged once for the whole order"
        col.addWidget(caption("📦 Packaging", tip))
        self.packaging_spin = MoneySpin(state.settings.currency_symbol)
        self.packaging_spin.setToolTip(tip)
        col.addWidget(self.packaging_spin)
        col.addSpacing(8)

        tip = "Profit added on top of total cost"
        col.addWidget(caption("📈 Margin", tip))
        row = QHBoxLayout()
        self.margin_slider = QSlider(Qt.Orientation.Horizontal)
        self.margin_slider.setRange(0, 500)
        self.margin_slider.setToolTip(tip)
        self.margin_spin = GuardedDoubleSpin()
        self.margin_spin.setRange(0, 500)
        self.margin_spin.setDecimals(1)
        self.margin_spin.setSuffix(" %")
        self.margin_spin.setToolTip(tip)
        row.addWidget(self.margin_slider, 1)
        row.addWidget(self.margin_spin)
        col.addLayout(row)
        col.addSpacing(8)

        tip = "Extra % on filament and electricity to cover failed prints"
        col.addWidget(caption("⚠️ Failure allowance", tip))
        self.failure_spin = GuardedDoubleSpin()
        self.failure_spin.setRange(0, 100)
        self.failure_spin.setDecimals(1)
        self.failure_spin.setSuffix(" %")
        self.failure_spin.setToolTip(tip)
        col.addWidget(self.failure_spin)
        col.addStretch(1)

        self.refresh()
        self.customer_edit.textEdited.connect(lambda t: state.update_job(customer=t))
        self.packaging_spin.valueChanged.connect(lambda v: state.update_job(packaging=v))
        self.margin_spin.valueChanged.connect(self._on_margin_spin)
        self.margin_slider.valueChanged.connect(self._on_margin_slider)
        self.failure_spin.valueChanged.connect(
            lambda v: state.update_settings(failure_pct=v))
        state.job_changed.connect(self.refresh)
        state.settings_changed.connect(self.refresh)

    def _on_margin_spin(self, v: float) -> None:
        self.margin_slider.blockSignals(True)
        self.margin_slider.setValue(round(v))
        self.margin_slider.blockSignals(False)
        self.state.update_settings(margin_pct=v)

    def _on_margin_slider(self, v: int) -> None:
        self.margin_spin.blockSignals(True)
        self.margin_spin.setValue(float(v))
        self.margin_spin.blockSignals(False)
        self.state.update_settings(margin_pct=float(v))

    def refresh(self) -> None:
        s, j = self.state.settings, self.state.job
        if self.customer_edit.text() != j.customer:
            self.customer_edit.setText(j.customer)
        self.packaging_spin.set_symbol(s.currency_symbol)
        for spin, val in ((self.packaging_spin, j.packaging),
                          (self.margin_spin, s.margin_pct),
                          (self.failure_spin, s.failure_pct)):
            if abs(spin.value() - val) > 1e-9:
                spin.blockSignals(True)
                spin.setValue(val)
                spin.blockSignals(False)
        if self.margin_slider.value() != round(s.margin_pct):
            self.margin_slider.blockSignals(True)
            self.margin_slider.setValue(round(s.margin_pct))
            self.margin_slider.blockSignals(False)
