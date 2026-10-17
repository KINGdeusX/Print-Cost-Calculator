"""Spin boxes and combos that ignore the mouse wheel unless focused."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QLineEdit, QSpinBox


def no_drops(widget) -> None:
    """Stop text widgets from swallowing file drops meant for the window."""
    widget.setAcceptDrops(False)
    for edit in widget.findChildren(QLineEdit):
        edit.setAcceptDrops(False)


class _WheelGuard:
    def _guard_init(self) -> None:
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event) -> None:
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()  # lets the surrounding scroll area scroll


class GuardedSpin(_WheelGuard, QSpinBox):
    def __init__(self, *a):
        super().__init__(*a)
        self._guard_init()
        no_drops(self)


class GuardedDoubleSpin(_WheelGuard, QDoubleSpinBox):
    def __init__(self, *a):
        super().__init__(*a)
        self._guard_init()
        no_drops(self)


class GuardedCombo(_WheelGuard, QComboBox):
    def __init__(self, *a):
        super().__init__(*a)
        self._guard_init()


class MoneySpin(GuardedDoubleSpin):
    def __init__(self, symbol: str = "", parent=None):
        super().__init__(parent)
        self.setRange(0.0, 1e9)
        self.setDecimals(2)
        self.setSingleStep(1.0)
        self.setGroupSeparatorShown(True)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.set_symbol(symbol)

    def set_symbol(self, symbol: str) -> None:
        self.setPrefix(f"{symbol} " if symbol else "")
