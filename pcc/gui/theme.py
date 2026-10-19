"""Theme tokens, QSS builder and application of the theme."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

TOKENS: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#F6F5F2", "surface": "#FFFFFF", "surface2": "#EFEDE8",
        "border": "#DDD9D1", "text": "#1F2328", "text_muted": "#5C6168",
        "accent": "#F26B1D", "accent_text": "#1A1208",
        "success": "#1E7F4A", "warning": "#9A5B00", "danger": "#C42B2B",
    },
    "dark": {
        "bg": "#16181C", "surface": "#1F2227", "surface2": "#292D33",
        "border": "#363B43", "text": "#ECEAE6", "text_muted": "#A4A9B1",
        "accent": "#FF8A3D", "accent_text": "#1A1208",
        "success": "#4CC38A", "warning": "#F2B34A", "danger": "#FF6B6B",
    },
}

_QSS_DIR = Path(__file__).resolve().parent.parent / "assets" / "qss"
_current_mode = "light"
FONT_STACK = '"Segoe UI", "Inter", "Noto Sans", sans-serif'


def current_mode() -> str:
    return _current_mode


def resolve_mode(theme: str, app: QGuiApplication) -> str:
    if theme in ("light", "dark"):
        return theme
    scheme = app.styleHints().colorScheme()
    return "dark" if scheme == Qt.ColorScheme.Dark else "light"


def build_qss(mode: str) -> str:
    t = TOKENS[mode]
    c = dict(t)
    # derived: hover/pressed tints and disabled colors
    c["accent_hover"] = _mix(t["accent"], t["text"], 0.10)
    c["accent_press"] = _mix(t["accent"], t["text"], 0.22)
    c["hover"] = _mix(t["surface2"], t["text"], 0.06)
    c["press"] = _mix(t["surface2"], t["text"], 0.12)
    c["dis_bg"] = _mix(t["bg"], t["surface2"], 0.5)
    c["dis_text"] = _mix(t["text_muted"], t["surface"], 0.45)
    c["sel_bg"] = _mix(t["surface"], t["accent"], 0.22)
    down = (_QSS_DIR / f"chevron-down-{mode}.svg").as_posix()
    up = (_QSS_DIR / f"chevron-up-{mode}.svg").as_posix()
    return f"""
* {{ font-family: {FONT_STACK}; font-size: 10.5pt; }}
QWidget {{ color: {c['text']}; }}
QMainWindow, QDialog, QMessageBox, QStackedWidget, QScrollArea {{ background: {c['bg']}; }}
QScrollArea {{ border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QWidget:disabled {{ color: {c['dis_text']}; }}
QLabel {{ background: transparent; }}
QLabel[muted="true"] {{ color: {c['text_muted']}; }}
QLabel[role="title"] {{ font-size: 15pt; font-weight: 700; }}
QLabel[thumb="true"] {{ background: {c['surface2']}; border: 1px solid {c['border']}; border-radius: 6px; }}
QToolButton[role="more"] {{ font-size: 16pt; font-weight: 700; padding: 0; }}
QLabel[dirty="true"] {{ color: {c['accent']}; font-weight: 600; }}
QLabel[role="price"] {{ font-size: 28px; font-weight: 700; }}
QFrame[card="true"] {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; }}
QFrame[card="true"] QLabel {{ background: transparent; border: none; }}
QFrame[banner="warning"] {{ background: {_mix(c['surface'], c['warning'], 0.14)}; border: 1px solid {c['warning']}; border-radius: 8px; }}
QFrame[banner="danger"] {{ background: {_mix(c['surface'], c['danger'], 0.14)}; border: 1px solid {c['danger']}; border-radius: 8px; }}
QFrame[banner] QLabel {{ background: transparent; border: none; }}

QPushButton {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 0 16px; min-height: 34px; }}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:pressed {{ background: {c['press']}; }}
QPushButton:focus {{ border: 2px solid {c['accent']}; padding: 0 15px; }}
QPushButton:disabled {{ background: {c['dis_bg']}; color: {c['dis_text']}; border-color: {c['border']}; }}
QPushButton[accent="true"] {{ background: {c['accent']}; color: {c['accent_text']}; border: 1px solid {c['accent']}; font-weight: 600; }}
QPushButton[accent="true"]:hover {{ background: {c['accent_hover']}; border-color: {c['accent_hover']}; }}
QPushButton[accent="true"]:pressed {{ background: {c['accent_press']}; border-color: {c['accent_press']}; }}
QPushButton[accent="true"]:focus {{ border: 2px solid {c['text']}; padding: 0 15px; }}
QPushButton[accent="true"]:disabled {{ background: {c['dis_bg']}; color: {c['dis_text']}; border-color: {c['border']}; }}

QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 6px; }}
QToolButton:hover {{ background: {c['hover']}; }}
QToolButton:pressed, QToolButton:checked {{ background: {c['press']}; }}
QToolButton:focus {{ border: 2px solid {c['accent']}; }}
QToolButton::menu-indicator {{ image: none; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 0 10px; min-height: 34px; selection-background-color: {c['accent']}; selection-color: {c['accent_text']}; }}
QPlainTextEdit, QTextEdit {{ padding: 6px 10px; }}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{ border-color: {c['text_muted']}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 2px solid {c['accent']}; padding: 0 9px; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ background: {c['dis_bg']}; color: {c['dis_text']}; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 28px; border: none; }}
QComboBox::down-arrow {{ image: url("{down}"); width: 14px; height: 14px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; width: 24px; border: none; margin: 3px 3px 0 0; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; width: 24px; border: none; margin: 0 3px 3px 0; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url("{up}"); width: 10px; height: 10px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url("{down}"); width: 10px; height: 10px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{ background: {c['hover']}; border-radius: 4px; }}
QComboBox QAbstractItemView {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 4px; outline: none; selection-background-color: {c['sel_bg']}; selection-color: {c['text']}; }}

QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {c['text_muted']}; border-radius: 4px; background: {c['surface']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}
QCheckBox::indicator:focus {{ border: 2px solid {c['accent']}; }}
QCheckBox::indicator:disabled {{ background: {c['dis_bg']}; border-color: {c['border']}; }}

QSlider:horizontal {{ min-height: 22px; }}
QSlider::groove:horizontal {{ height: 6px; background: {c['surface2']}; border: 1px solid {c['border']}; border-radius: 4px; }}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 4px; }}
QSlider::handle:horizontal {{ width: 16px; height: 16px; margin: -7px 0; background: {c['surface']}; border: 2px solid {c['accent']}; border-radius: 9px; }}
QSlider::handle:horizontal:hover {{ background: {c['sel_bg']}; }}
QSlider::handle:horizontal:focus {{ border-color: {c['text']}; }}
QSlider::groove:horizontal:disabled, QSlider::sub-page:horizontal:disabled {{ background: {c['dis_bg']}; }}
QSlider::handle:horizontal:disabled {{ border-color: {c['dis_text']}; background: {c['dis_bg']}; }}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 4px; min-width: 28px; }}
QScrollBar::handle:hover {{ background: {c['text_muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QMenu {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 7px 22px 7px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['sel_bg']}; color: {c['text']}; }}
QMenu::item:disabled {{ color: {c['dis_text']}; background: transparent; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 5px 8px; }}
QToolTip {{ background: {c['surface2']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 5px 8px; }}

QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 8px; background: {c['surface']}; top: -1px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; color: {c['text_muted']}; padding: 8px 16px; border: none; border-bottom: 2px solid transparent; margin-right: 4px; }}
QTabBar::tab:hover {{ color: {c['text']}; }}
QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; font-weight: 600; }}

QListWidget, QListView, QTreeView, QTableView {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 4px; outline: none; alternate-background-color: {c['surface2']}; }}
QListWidget::item {{ padding: 8px 10px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {c['hover']}; }}
QListWidget::item:selected {{ background: {c['sel_bg']}; color: {c['text']}; }}
QHeaderView::section {{ background: {c['surface2']}; color: {c['text_muted']}; border: none; border-bottom: 1px solid {c['border']}; padding: 6px 10px; }}

QSplitter::handle {{ background: {c['border']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QSplitter::handle:hover {{ background: {c['accent']}; }}
QStatusBar {{ background: {c['surface']}; color: {c['text_muted']}; border-top: 1px solid {c['border']}; }}
QStatusBar::item {{ border: none; }}
QMessageBox QLabel {{ background: transparent; }}
QProgressBar {{ background: {c['surface2']}; border: 1px solid {c['border']}; border-radius: 6px; text-align: center; min-height: 12px; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 5px; }}
"""


def _mix(a: str, b: str, t: float) -> str:
    """Blend colour a toward b by fraction t; returns #RRGGBB."""
    ca, cb = QColor(a), QColor(b)
    ch = [round(x + (y - x) * t) for x, y in
          ((ca.red(), cb.red()), (ca.green(), cb.green()), (ca.blue(), cb.blue()))]
    return "#{:02X}{:02X}{:02X}".format(*ch)


def _palette(mode: str) -> QPalette:
    t = TOKENS[mode]
    p = QPalette()
    R = QPalette.ColorRole
    for role, key in (
        (R.Window, "bg"), (R.WindowText, "text"), (R.Base, "surface"),
        (R.AlternateBase, "surface2"), (R.Text, "text"), (R.Button, "surface"),
        (R.ButtonText, "text"), (R.ToolTipBase, "surface2"), (R.ToolTipText, "text"),
        (R.Highlight, "accent"), (R.HighlightedText, "accent_text"),
        (R.PlaceholderText, "text_muted"), (R.Link, "accent"),
    ):
        p.setColor(role, QColor(t[key]))
    dis = QColor(_mix(t["text_muted"], t["surface"], 0.45))
    for role in (R.WindowText, R.Text, R.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, dis)
    return p


def apply_theme(app, theme: str) -> str:
    global _current_mode
    mode = resolve_mode(theme, app)
    _current_mode = mode
    app.setStyle("Fusion")
    app.setPalette(_palette(mode))
    app.setStyleSheet(build_qss(mode))
    return mode
