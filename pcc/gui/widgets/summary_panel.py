"""Live cost breakdown, final price and export button."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from pcc.core.currency import format_money

_LINES = (
    ("filament", "🧵 Filament"), ("electricity", "⚡ Electricity"),
    ("failure", "⚠️ Failure allowance"), ("labor", "🛠 Labor"),
)
_R = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class SummaryPanel(QFrame):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setProperty("card", True)
        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(8)
        head = QLabel("💰 Summary")
        f = head.font()
        f.setBold(True)
        head.setFont(f)
        col.addWidget(head)

        self._plate_grid = QGridLayout()
        self._plate_grid.setHorizontalSpacing(12)
        self._plate_grid.setVerticalSpacing(4)
        self._plate_grid.setColumnStretch(0, 1)
        col.addLayout(self._plate_grid)
        self._sep = QFrame()
        self._sep.setFixedHeight(1)
        self._sep.setStyleSheet("background: rgba(128,128,128,70); border: none;")
        col.addWidget(self._sep)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(0, 1)
        self._values: dict[str, QLabel] = {}
        r = 0
        for key, text in (*_LINES, ("packaging", "📦 Packaging")):
            grid.addWidget(QLabel(text), r, 0)
            v = QLabel()
            v.setAlignment(_R)
            grid.addWidget(v, r, 1)
            self._values[key] = v
            r += 1
        self.internal_fee_label = QLabel()
        self.internal_fee_label.setProperty("muted", True)
        self.internal_fee_label.setToolTip("Not shown in exports")
        self.internal_fee_label.setAlignment(_R)
        grid.addWidget(self.internal_fee_label, r, 0, 1, 2)
        col.addLayout(grid)
        col.addSpacing(8)

        tl = QLabel("💵 Price")
        tl.setToolTip("Total cost plus margin, rounded")
        col.addWidget(tl)
        self.price_label = QLabel()
        self.price_label.setProperty("role", "price")
        self.price_label.setAlignment(_R)
        self.price_label.setToolTip("Total cost plus margin, rounded")
        col.addWidget(self.price_label)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("muted", True)
        col.addWidget(self.error_label)
        col.addStretch(1)
        self.export_button = QPushButton("📤 Export")
        self.export_button.setProperty("accent", True)
        self.export_button.setToolTip("Save this quote to an Excel report")
        self.export_button.setEnabled(False)
        col.addWidget(self.export_button)

        state.quote_changed.connect(self.refresh)
        state.settings_changed.connect(self.refresh)
        self.refresh()

    def _clear_plates(self) -> None:
        while self._plate_grid.count():
            w = self._plate_grid.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()

    def refresh(self, *_) -> None:
        sym = self.state.settings.currency_symbol
        q = self.state.quote
        self._clear_plates()
        self.error_label.setText((self.state.last_error or "") if q is None else "")
        self.error_label.setVisible(q is None and bool(self.state.last_error))
        self.export_button.setEnabled(q is not None)
        if q is None:
            for v in self._values.values():
                v.setText("—")
            self.internal_fee_label.hide()
            self.price_label.setText("—")
            return
        for i, pb in enumerate(q.plates):
            n = QLabel(f"{pb.name} ×{pb.copies}")
            n.setToolTip(pb.name)
            p = QLabel(format_money(pb.price_total, sym))
            p.setAlignment(_R)
            self._plate_grid.addWidget(n, i, 0)
            self._plate_grid.addWidget(p, i, 1)
        for key, _t in _LINES:
            self._values[key].setText(format_money(getattr(q.lines, key), sym))
        self._values["packaging"].setText(format_money(q.packaging, sym))
        if q.internal_fee:
            self.internal_fee_label.setText(
                f"🔒 Internal fee  {format_money(q.internal_fee, sym)}")
            self.internal_fee_label.show()
        else:
            self.internal_fee_label.hide()
        self.price_label.setText(format_money(q.price, sym))
