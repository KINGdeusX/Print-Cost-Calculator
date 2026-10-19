"""Settings: costs, pricing and appearance."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QPalette, QPixmap
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from pcc.core.currency import CURRENCIES
from pcc.core.paths import projects_dir
from pcc.gui import logo
from pcc.gui.icons import app_icon
from pcc.gui.widgets.money_spin import (
    GuardedCombo, GuardedDoubleSpin, MoneySpin, fill_currency_combo,
)

HIDDEN_FEE_HELP = "Added to each plate's price after margin. Never shown in exports."
_ROUNDING = (0, 1, 5, 10, 50, 100)
_LOGO_BOX = 150
_MAX_BODY_HEIGHT = 620
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
    def __init__(self, state, parent=None, focus_company: bool = False):
        super().__init__(parent)
        self.state = state
        s = state.settings
        self._currency = (s.currency_code, s.currency_symbol)
        self._pending_logo: bytes | None = None
        self._remove_logo = False
        self.setWindowTitle("Settings")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(580)

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

        self.company_edit = QLineEdit()
        self.company_edit.setPlaceholderText("Shown on your invoices")
        self.company_edit.setToolTip("Your business name, printed on invoices")
        self.logo_preview = QLabel()
        self.logo_preview.setFixedSize(_LOGO_BOX, _LOGO_BOX)
        self.logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_preview.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self.logo_preview.setStyleSheet(
            "border: 1px solid rgba(128, 128, 128, 90); border-radius: 6px;")
        self.logo_upload_button = QPushButton("Upload…")
        self.logo_upload_button.setToolTip("Choose an image to print on invoices")
        self.logo_upload_button.clicked.connect(self._upload_logo)
        self.logo_remove_button = QPushButton("Remove")
        self.logo_remove_button.setToolTip("Stop printing a logo on invoices")
        self.logo_remove_button.clicked.connect(self._remove_logo_clicked)
        self.logo_error_label = QLabel()
        self.logo_error_label.setStyleSheet("color: #d64545;")
        self.logo_error_label.setWordWrap(True)
        self.logo_error_label.hide()
        logo_buttons = QHBoxLayout()
        logo_buttons.addWidget(self.logo_upload_button)
        logo_buttons.addWidget(self.logo_remove_button)
        logo_buttons.addStretch(1)
        logo_col = QVBoxLayout()
        logo_col.setSpacing(6)
        logo_col.addWidget(self.logo_preview)
        logo_col.addLayout(logo_buttons)
        logo_col.addWidget(self.logo_error_label)
        logo_box = QWidget()
        logo_box.setLayout(logo_col)
        logo_col.setContentsMargins(0, 0, 0, 0)
        self.data_folder_label = QLabel(str(projects_dir(create=False)))
        self.data_folder_label.setWordWrap(True)
        self.data_folder_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self.open_data_folder_button = QPushButton("Open folder")
        self.open_data_folder_button.setToolTip("Show your saved projects in the file manager")
        self.open_data_folder_button.clicked.connect(self._open_data_folder)
        folder_box = QWidget()
        folder_row = QHBoxLayout(folder_box)
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.addWidget(self.data_folder_label, 1)
        folder_row.addWidget(self.open_data_folder_button)

        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)
        self.company_section = self._section("🏢 Company", [
            ("Company name", self.company_edit),
            ("Logo", logo_box),
            ("Projects folder", folder_box),
        ])
        col.addWidget(self.company_section)
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
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(body)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        outer = QVBoxLayout(self)
        outer.setSpacing(12)
        outer.addWidget(self.scroll, 1)
        outer.addWidget(self.buttons)
        # Tall content scrolls; OK/Cancel stay visible below it.
        self.scroll.setMinimumHeight(min(body.sizeHint().height() + 4, _MAX_BODY_HEIGHT))

        self._load(s)
        self._show_logo(logo.read_logo())
        if focus_company:
            QTimer.singleShot(0, self._focus_company)
        self.currency_combo.currentIndexChanged.connect(self._on_currency)

    def _focus_company(self) -> None:
        self.scroll.ensureWidgetVisible(self.company_section)
        self.company_edit.setFocus()

    # -- logo -----------------------------------------------------------
    def _show_logo(self, data: bytes | None) -> None:
        img = QImage.fromData(data) if data else QImage()
        if img.isNull():
            self.logo_preview.setPixmap(QPixmap())
            self.logo_preview.setText("No logo")
        else:
            if img.width() > _LOGO_BOX or img.height() > _LOGO_BOX:
                img = img.scaled(_LOGO_BOX - 2, _LOGO_BOX - 2,
                                 Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            self.logo_preview.setPixmap(QPixmap.fromImage(img))
        self.logo_remove_button.setEnabled(not img.isNull())

    def _upload_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a logo", "", logo.image_filter())
        if not path:
            return
        try:
            data = logo.load_logo_image(path)
        except logo.LogoError as e:
            self.logo_error_label.setText(str(e))
            self.logo_error_label.show()
            return
        self.logo_error_label.hide()
        self._pending_logo = data
        self._remove_logo = False
        self._show_logo(data)

    def _remove_logo_clicked(self) -> None:
        self.logo_error_label.hide()
        self._pending_logo = None
        self._remove_logo = True
        self._show_logo(None)

    def _open_data_folder(self) -> None:
        try:
            folder = projects_dir()
        except OSError:  # can't be created: the file manager reports it
            folder = projects_dir(create=False)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

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
        self.company_edit.setText(s.company_name)
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
            "company_name": self.company_edit.text().strip(),
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
        if self._pending_logo is not None:
            logo.save_logo(self._pending_logo)
        elif self._remove_logo:
            logo.remove_logo()
        changed = self.changed_fields()
        if changed:
            self.state.update_settings(**changed)
        super().accept()
