import base64

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from pcc.gui.main_window import MainWindow
from pcc.gui.state import AppState


def make(qtbot):
    state = AppState(legacy_paths=[])
    w = MainWindow(state)
    qtbot.addWidget(w)
    return state, w


def test_window_builds(qtbot, cfg_dir):
    state, w = make(qtbot)
    assert w.windowTitle() == "Print Cost Calculator"
    assert w.printer_combo.count() >= 15
    assert w.job_area.objectName() == "job_area"
    assert not w.windowIcon().isNull()


def test_printer_selection_updates_job(qtbot, cfg_dir):
    state, w = make(qtbot)
    w.printer_combo.setCurrentIndex(3)
    assert state.job.printer_id == state.catalog.printers[3].id


def test_theme_cycle_persists(qtbot, cfg_dir):
    state, w = make(qtbot)
    assert state.settings.theme == "system"
    w.theme_button.click()
    assert state.settings.theme == "light"
    assert w.theme_button.toolTip() == "Theme: Light"
    w.theme_button.click()
    assert state.settings.theme == "dark"
    assert w.theme_button.toolTip() == "Theme: Dark"
    w.theme_button.click()
    assert state.settings.theme == "system"
    assert w.theme_button.toolTip() == "Theme: System"


def test_currency_change(qtbot, cfg_dir):
    state, w = make(qtbot)
    i = w.currency_combo.findText("€ EUR")
    assert i >= 0
    w.currency_combo.setCurrentIndex(i)
    assert state.settings.currency_symbol == "€"
    assert state.settings.currency_code == "EUR"


def test_currency_custom(qtbot, cfg_dir, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Ƀ", True))
    state, w = make(qtbot)
    w.currency_combo.setCurrentIndex(w.currency_combo.findText("Custom…"))
    assert state.settings.currency_code == "XXX"
    assert state.settings.currency_symbol == "Ƀ"
    assert w.currency_combo.currentText() == "Ƀ XXX"


def test_currency_custom_cancel_restores(qtbot, cfg_dir, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    state, w = make(qtbot)
    w.currency_combo.setCurrentIndex(w.currency_combo.findText("Custom…"))
    assert state.settings.currency_code == "PHP"
    assert w.currency_combo.currentText() == "₱ PHP"


def test_combos_refresh_without_emitting(qtbot, cfg_dir):
    state, w = make(qtbot)
    state.update_settings(currency_code="USD", currency_symbol="$")
    assert w.currency_combo.currentText() == "$ USD"
    assert state.settings.currency_code == "USD"


def test_compact_layout(qtbot, cfg_dir):
    state, w = make(qtbot)
    w.resize(900, 700)
    assert w.is_compact()
    w.resize(1300, 800)
    assert not w.is_compact()
    w.resize(900, 700)
    assert w.is_compact()
    assert w.summary_area.parent() is not w.plates_area.parent()


def test_warning_shown_in_banner(qtbot, cfg_dir):
    state, w = make(qtbot)
    w.show()
    state.warning.emit("careful")
    assert w.banner.isVisible()
    assert "careful" in w.banner.label.text()


def test_geometry_saved_on_close(qtbot, cfg_dir):
    state, w = make(qtbot)
    w.show()
    w.resize(760, 600)
    w.close()
    assert state.settings.window_geometry
    base64.b64decode(state.settings.window_geometry)
    state2, w2 = make(qtbot)
    w2.show()
    assert w2.size().width() == 760


def test_main_timing_smoke(capsys, cfg_dir, monkeypatch):
    from pcc.gui import app as appmod

    def fake_exec(*a):
        QApplication.processEvents()
        return 0

    monkeypatch.setattr(QApplication, "exec", fake_exec)
    QApplication.instance() or QApplication([])
    assert appmod.main(["--timing"]) == 0
    err = capsys.readouterr().err
    for stage in ("qt", "splash", "state", "window", "shown"):
        assert f"[timing] {stage}: " in err
