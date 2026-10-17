from PySide6.QtWidgets import QApplication, QLabel

from pcc.core.models import Catalog, Filament
from pcc.gui.dialogs.filaments_dialog import FilamentsDialog
from pcc.gui.dialogs.printers_dialog import PrintersDialog
from pcc.gui.dialogs.settings_dialog import SettingsDialog
from pcc.gui.main_window import MainWindow
from pcc.gui.state import AppState


def make_state(cfg_dir):
    return AppState(legacy_paths=[])


def test_settings_dialog_saves(qtbot, cfg_dir):
    state = make_state(cfg_dir)
    seen = []
    state.settings_changed.connect(lambda: seen.append(1))
    d = SettingsDialog(state)
    qtbot.addWidget(d)
    d.fee_spin.setValue(30)
    assert d.changed_fields() == {"hidden_plate_fee": 30.0}
    d.accept()
    assert state.settings.hidden_plate_fee == 30
    assert len(seen) == 1


def test_settings_dialog_no_change_no_update(qtbot, cfg_dir):
    state = make_state(cfg_dir)
    seen = []
    state.settings_changed.connect(lambda: seen.append(1))
    d = SettingsDialog(state)
    qtbot.addWidget(d)
    d.accept()
    assert seen == []


def test_settings_dialog_cancel(qtbot, cfg_dir):
    state = make_state(cfg_dir)
    d = SettingsDialog(state)
    qtbot.addWidget(d)
    d.fee_spin.setValue(30)
    d.theme_combo.setCurrentIndex(2)
    d.reject()
    assert state.settings.hidden_plate_fee == 0
    assert state.settings.theme == "system"


def test_settings_dialog_copy_and_fields(qtbot, cfg_dir):
    state = make_state(cfg_dir)
    d = SettingsDialog(state)
    qtbot.addWidget(d)
    assert d.rate_spin.suffix() == " ₱/kWh"
    assert [d.theme_combo.itemText(i) for i in range(3)] == ["System", "Light", "Dark"]
    texts = {w.text() for w in d.findChildren(QLabel)}
    assert {"⚡ Costs", "📈 Pricing", "🎨 Appearance",
            "Added to each plate's price after margin. Never shown in exports."} <= texts
    d.currency_combo.setCurrentIndex(d.currency_combo.findData("USD"))
    assert d.rate_spin.suffix() == " $/kWh"
    d.accept()
    assert state.settings.currency_code == "USD" and state.settings.currency_symbol == "$"


def test_cannot_delete_last_filament(qtbot, cfg_dir):
    state = make_state(cfg_dir)
    state.catalog = Catalog(
        printers=state.catalog.printers,
        filaments=[Filament("pla", "PLA", "PLA", 800.0, is_default=True)])
    d = FilamentsDialog(state)
    qtbot.addWidget(d)
    assert not d.delete_button.isEnabled()
    d.add_button.click()
    d.list.setCurrentRow(0)
    assert d.delete_button.isEnabled()


def test_delete_in_use_printer_falls_back(qtbot, cfg_dir):
    state = make_state(cfg_dir)
    default = state.catalog.default_printer().id
    victim = state.catalog.printers[3].id
    state.update_job(printer_id=victim)
    warnings = []
    state.warning.connect(warnings.append)
    d = PrintersDialog(state)
    qtbot.addWidget(d)
    d.list.setCurrentRow(3)
    d.delete_button.click()
    assert state.catalog.printer(victim) is not None  # still a copy
    d.accept()
    assert state.job.printer_id == default
    assert warnings and "default" in warnings[0]


def test_cancel_discards_catalog_edits(qtbot, cfg_dir):
    state = make_state(cfg_dir)
    n = len(state.catalog.printers)
    d = PrintersDialog(state)
    qtbot.addWidget(d)
    d.delete_button.click()
    d.name_edit.setText("x")
    d.name_edit.textEdited.emit("x")
    d.reject()
    assert len(state.catalog.printers) == n


def test_add_printer_appears_in_combo(qtbot, cfg_dir):
    state = make_state(cfg_dir)
    w = MainWindow(state)
    qtbot.addWidget(w)
    d = PrintersDialog(state, w)
    qtbot.addWidget(d)
    d.add_button.click()
    d.name_edit.setText("My Printer")
    d.name_edit.textEdited.emit("My Printer")
    d.watts_spin.setValue(222)
    d.match_edit.setText(" P1S, ,X1C ")
    d.match_edit.textEdited.emit(" P1S, ,X1C ")
    d.accept()
    assert w.printer_combo.findText("My Printer") >= 0
    p = state.catalog.printers[-1]
    assert (p.watts, p.model_match) == (222.0, ["P1S", "X1C"])
    assert p.id.startswith("printer-")


def test_empty_name_disables_ok(qtbot, cfg_dir):
    state = make_state(cfg_dir)
    d = PrintersDialog(state)
    qtbot.addWidget(d)
    d.name_edit.setText("")
    d.name_edit.textEdited.emit("")
    assert not d.ok_button.isEnabled()
    d.name_edit.setText("ok")
    d.name_edit.textEdited.emit("ok")
    assert d.ok_button.isEnabled()


def test_filament_default_color_duplicate(qtbot, cfg_dir):
    state = make_state(cfg_dir)
    d = FilamentsDialog(state)
    qtbot.addWidget(d)
    d.list.setCurrentRow(1)
    d.set_default_button.click()
    assert d.catalog.default_filament().id == d.catalog.filaments[1].id
    assert "★ default" in d.list.item(1).text()
    d.set_color("#112233")
    d.duplicate_button.click()
    dup = d.catalog.filaments[2]
    assert dup.color == "#112233" and not dup.is_default and dup.id.startswith("filament-")
    d.accept()
    assert state.catalog.default_filament().id == state.catalog.filaments[1].id


def _printer_window(qtbot, cfg_dir, monkeypatch):
    state = make_state(cfg_dir)
    w = MainWindow(state)
    qtbot.addWidget(w)
    opened = []
    monkeypatch.setattr(MainWindow, "open_printers_dialog", lambda self: opened.append(1))
    return state, w, opened


def test_manage_items_do_not_select(qtbot, cfg_dir, monkeypatch):
    state, w, opened = _printer_window(qtbot, cfg_dir, monkeypatch)
    c = w.printer_combo
    before = c.currentIndex()
    assert c.itemText(c.count() - 1) == "✏️ Manage printers…"
    c.activated.emit(c.count() - 1)  # picked from the popup
    assert opened == [1] and c.currentIndex() == before
    assert state.job.printer_id == state.catalog.printers[before].id


def test_manage_printers_not_opened_by_mere_index_change(qtbot, cfg_dir, monkeypatch):
    state, w, opened = _printer_window(qtbot, cfg_dir, monkeypatch)
    c = w.printer_combo
    before = c.currentIndex()
    c.setCurrentIndex(c.count() - 1)
    assert opened == []
    qtbot.waitUntil(lambda: c.currentIndex() == before, timeout=1000)
    assert state.job.printer_id == state.catalog.printers[before].id


def test_manage_printers_not_opened_by_arrow_keys(qtbot, cfg_dir, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    state, w, opened = _printer_window(qtbot, cfg_dir, monkeypatch)
    w.show()
    c = w.printer_combo
    last = len(state.catalog.printers) - 1
    c.setCurrentIndex(last)
    assert state.job.printer_id == state.catalog.printers[last].id
    c.setFocus()
    QTest.keyClick(c, Qt.Key.Key_Down)  # onto "Manage printers…" (separator skipped)
    QApplication.processEvents()
    assert opened == [] and c.currentIndex() == last
    assert state.job.printer_id == state.catalog.printers[last].id
    QTest.keyClick(c, Qt.Key.Key_Up)  # arrows still change the printer
    assert state.job.printer_id == state.catalog.printers[last - 1].id


def test_filament_row_manage_item(qtbot, cfg_dir, monkeypatch):
    from pcc.gui.widgets.plate_card import PlateCard
    state = make_state(cfg_dir)
    plate = state.add_plate()
    card = PlateCard(state, plate.id)
    qtbot.addWidget(card)
    opened = []
    monkeypatch.setattr(PlateCard, "open_filaments_dialog", lambda self: opened.append(1))
    row = card.rows[0]
    cb = row.combo
    cur = cb.currentIndex()
    assert cb.itemText(cb.count() - 1) == "✏️ Manage filaments…"
    cb.activated.emit(cb.count() - 1)
    assert opened == [1] and cb.currentIndex() == cur
    assert state.job.plates[0].filaments[0].filament_id == cb.itemData(cur)


def test_filament_manage_not_opened_by_arrow_keys(qtbot, cfg_dir, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from pcc.gui.widgets.plate_card import PlateCard
    state = make_state(cfg_dir)
    plate = state.add_plate()
    card = PlateCard(state, plate.id)
    qtbot.addWidget(card)
    card.show()
    opened = []
    monkeypatch.setattr(PlateCard, "open_filaments_dialog", lambda self: opened.append(1))
    cb = card.rows[0].combo
    last = cb.findData(state.catalog.filaments[-1].id)
    cb.setCurrentIndex(last)
    cb.activated.emit(last)
    cb.setFocus()
    QTest.keyClick(cb, Qt.Key.Key_Down)
    QApplication.processEvents()
    assert opened == [] and cb.currentIndex() == last
    assert state.job.plates[0].filaments[0].filament_id == state.catalog.filaments[-1].id


def test_settings_button_opens_dialog(qtbot, cfg_dir, monkeypatch):
    state = make_state(cfg_dir)
    w = MainWindow(state)
    qtbot.addWidget(w)
    opened = []
    monkeypatch.setattr(SettingsDialog, "exec", lambda self: opened.append(1) or 0)
    w.settings_button.click()
    assert opened == [1]
