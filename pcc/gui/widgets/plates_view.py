"""Scrollable column of plate cards with add / import buttons."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from pcc.gui.icons import icon
from pcc.gui.widgets.plate_card import PlateCard

EMPTY_TEXT = "Drop a sliced .3mf or add a plate"


class PlatesView(QWidget):
    import_requested = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 0, 8, 0)
        outer.setSpacing(10)
        head = QLabel("🧩 Plates")
        f = head.font()
        f.setBold(True)
        head.setFont(f)
        outer.addWidget(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        inner = QWidget()
        self._cards_box = QVBoxLayout(inner)
        self._cards_box.setContentsMargins(0, 0, 6, 0)
        self._cards_box.setSpacing(12)

        self.empty_state = QWidget()
        es = QVBoxLayout(self.empty_state)
        es.setSpacing(12)
        es.addStretch(1)
        pic = QLabel()
        pic.setPixmap(icon("import", size=48).pixmap(48, 48))
        pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label = QLabel(EMPTY_TEXT)
        self.empty_label.setProperty("muted", True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        es.addWidget(pic)
        es.addWidget(self.empty_label)
        es.addStretch(1)
        self._cards_box.addWidget(self.empty_state, 1)
        self._cards_box.addStretch(0)  # keeps cards packed at the top
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll, 1)

        row = QHBoxLayout()
        self.add_button = QPushButton("➕ Add plate")
        self.add_button.setToolTip("Add a plate and type in its time and filament")
        self.import_button = QPushButton("📂 Import")
        self.import_button.setToolTip("Import sliced .3mf files (or drop them anywhere)")
        row.addWidget(self.add_button)
        row.addWidget(self.import_button)
        row.addStretch(1)
        outer.addLayout(row)

        self._cards: dict[str, PlateCard] = {}
        self.add_button.clicked.connect(lambda: state.add_plate())
        self.import_button.clicked.connect(self.import_requested)
        state.job_changed.connect(self.sync)
        state.catalog_changed.connect(self.sync)
        state.settings_changed.connect(self.sync)
        self.sync()

    def cards(self) -> list[PlateCard]:
        return [self._cards[p.id] for p in self.state.job.plates if p.id in self._cards]

    def sync(self) -> None:
        """Add/remove cards for structural changes; otherwise only refresh values."""
        plates = self.state.job.plates
        ids = [p.id for p in plates]
        for pid in [i for i in self._cards if i not in ids]:
            card = self._cards.pop(pid)
            self._cards_box.removeWidget(card)
            card.hide()
            card.deleteLater()
        for pos, p in enumerate(plates):
            card = self._cards.get(p.id)
            if card is None:
                card = PlateCard(self.state, p.id)
                self._cards[p.id] = card
                self._cards_box.insertWidget(pos, card)
            else:
                card.refresh()
        self.empty_state.setVisible(not plates)
