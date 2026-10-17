"""Settings: costs, pricing and appearance."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QFrame, QInputDialog, QLabel,
    QVBoxLayout,
)

from pcc.core.currency import CURRENCIES
from pcc.gui.icons import app_icon
from pcc.gui.widgets.money_spin import (
    GuardedCombo, GuardedDoubleSpin, MoneySpin, fill_currency_combo,
)

HIDDEN_FEE_HELP = "Added to each plate's price after margin. Never shown in exports."
_ROUNDING = (0, 1, 5, 10, 50, 100)
_THEMES = (("System", "system"), ("Light", "light"), ("Dark", "dark"))


def _muted(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("muted", True)
    lab.setWordWrap(True)
    return lab


def _percent_spin(tip: str) -> GuardedDoubleSpin:
    s = GuardedDoubleSpin()
    s.setRange(0, 1000)
    s.setDecimals(1)
    s.setSuffix(" %")
    s.setToolTip(tip)
    return s


class SettingsDialog(QDialog):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        s = state.settings
        self._currency = (s.currency_code, s.currency_symbol)
        self.setWindowTitle("Settings")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(460)

        self.rate_spin = MoneySpin()
        self.rate_spin.setToolTip("What you pay for electricity per kilowatt-hour")
        self.labor_spin = MoneySpin()
        self.labor_spin.setToolTip("Labor cost filled in for each new plate")
        self.packaging_spin = MoneySpin()
        self.packaging_spin.setToolTip("Packaging cost filled in for each new job")
        self.margin_spin = _percent_spin("Profit added on top of your costs")
        self.failure_spin = _percent_spin(
            "Extra filament and electricity to cover failed prints")
        self.fee_spin = MoneySpin()
        self.fee_spin.setToolTip(HIDDEN_FEE_HELP)
        self.rounding_combo = GuardedCombo()
        self.rounding_combo.setToolTip(
            "Round each final price to the nearest multiple of this amount")
        for step in _ROUNDING:
            self.rounding_combo.addItem("No rounding" if step == 0 else str(step), float(step))
        self.theme_combo = GuardedCombo()
        self.theme_combo.setToolTip("Light, dark, or follow your system")
        for label, value in _THEMES:
            self.theme_combo.addItem(label, value)
        self.currency_combo = GuardedCombo()
        self.currency_combo.setToolTip("Currency used for all prices")

        col = QVBoxLayout(self)
        col.setSpacing(12)
        col.addWidget(self._section("⚡ Costs", [
            ("Electricity rate", self.rate_spin),
            ("Default labor (per plate)", self.labor_spin),
            ("Default packaging (per job)", self.packaging_spin),
        ]))
        col.addWidget(self._section("📈 Pricing", [
            ("Margin", self.margin_spin),
            ("Failure allowance", self.failure_spin),
            ("🔒 Hidden plate fee", self.fee_spin),
            (None, _muted(HIDDEN_FEE_HELP)),
            ("Round price to", self.rounding_combo),
        ]))
        col.addWidget(self._section("🎨 Appearance", [
            ("Theme", self.theme_combo),
            ("Currency", self.currency_combo),
        ]))
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        col.addWidget(self.buttons)

        self._load(s)
        self.currency_combo.currentIndexChanged.connect(self._on_currency)

    @staticmethod
    def _section(title: str, rows) -> QFrame:
        card = QFrame()
        card.setProperty("card", True)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 12, 16, 14)
        head = QLabel(title)
        f = head.font()
        f.setBold(True)
        head.setFont(f)
        outer.addWidget(head)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        for label, widget in rows:
            if label is None:
                form.addRow(widget)
            else:
                lab = QLabel(label)
                lab.setToolTip(widget.toolTip())
                lab.setMinimumWidth(190)
                form.addRow(lab, widget)
        outer.addLayout(form)
        return card

    # -- values ---------------------------------------------------------
    def _load(self, s) -> None:
        self.rate_spin.setValue(s.electricity_rate)
        self.labor_spin.setValue(s.default_labor)
        self.packaging_spin.setValue(s.default_packaging)
        self.margin_spin.setValue(s.margin_pct)
        self.failure_spin.setValue(s.failure_pct)
        self.fee_spin.setValue(s.hidden_plate_fee)
        i = self.rounding_combo.findData(float(s.rounding_step))
        if i < 0:
            self.rounding_combo.addItem(f"{s.rounding_step:g}", float(s.rounding_step))
            i = self.rounding_combo.count() - 1
        self.rounding_combo.setCurrentIndex(i)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(s.theme)))
        fill_currency_combo(self.currency_combo, *self._currency)
        self._apply_symbol()
        self._initial = self._values()

    def _apply_symbol(self) -> None:
        sym = self._currency[1]
        self.rate_spin.setSuffix(f" {sym}/kWh")
        for sp in (self.labor_spin, self.packaging_spin, self.fee_spin):
            sp.set_symbol(sym)

    def _values(self) -> dict:
        code, sym = self._currency
        return {
            "electricity_rate": self.rate_spin.value(),
            "default_labor": self.labor_spin.value(),
            "default_packaging": self.packaging_spin.value(),
            "margin_pct": self.margin_spin.value(),
            "failure_pct": self.failure_spin.value(),
            "hidden_plate_fee": self.fee_spin.value(),
            "rounding_step": self.rounding_combo.currentData(),
            "theme": self.theme_combo.currentData(),
            "currency_code": code,
            "currency_symbol": sym,
        }

    def _on_currency(self, index: int) -> None:
        code = self.currency_combo.itemData(index)
        if code is None:
            sym, ok = QInputDialog.getText(
                self, "Custom currency", "Currency symbol:", text=self._currency[1])
            sym = sym.strip()
            if ok and sym:
                self._currency = ("XXX", sym)
            fill_currency_combo(self.currency_combo, *self._currency)
        else:
            sym = next((s for c, s, _ in CURRENCIES if c == code), self._currency[1])
            self._currency = (code, sym)
        self._apply_symbol()

    def changed_fields(self) -> dict:
        now = self._values()
        return {k: v for k, v in now.items() if v != self._initial[k]}

    def accept(self) -> None:
        changed = self.changed_fields()
        if changed:
            self.state.update_settings(**changed)
        super().accept()
