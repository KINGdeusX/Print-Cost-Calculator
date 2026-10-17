from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent

from pcc.core.currency import format_money
from pcc.gui.main_window import MainWindow
from pcc.gui.state import AppState
from tests.fixtures.make3mf import MULTI_PLATE_PROJECT


def make_window(qtbot):
    w = MainWindow(AppState(legacy_paths=[]))
    qtbot.addWidget(w)
    w.show()
    return w


def _file(tmp_path, name="p.3mf", data=MULTI_PLATE_PROJECT):
    f = tmp_path / name
    f.write_bytes(data)
    return f


def test_import_fills_cards_and_summary(qtbot, cfg_dir, tmp_path):
    w = make_window(qtbot)
    w.import_files([_file(tmp_path)])
    assert len(w.plates_view.cards()) == 2
    assert w.summary.price_label.text() == format_money(w.state.quote.price, "₱")
    assert w.toast.isVisible()


def test_drop_event_imports(qtbot, cfg_dir, tmp_path):
    w = make_window(qtbot)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(_file(tmp_path, "P.3MF")))])
    ev = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime,
                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    w.dropEvent(ev)
    assert len(w.plates_view.cards()) == 2
    assert not w.drop_overlay.isVisible()


def test_badge_for_type_match(qtbot, cfg_dir, tmp_path):
    w = make_window(qtbot)
    w.import_files([_file(tmp_path)])
    rows = [r for c in w.plates_view.cards() for r in c.rows]
    badged = [r for r in rows if not r.badge.isHidden()]
    assert badged
    r = badged[0]
    card = r.card
    r.combo.activated.emit(0)
    assert r.badge.isHidden()
    assert card.plate.filaments[r.index].match == "manual"


def test_bad_file_banner(qtbot, cfg_dir, tmp_path):
    w = make_window(qtbot)
    w.import_files([_file(tmp_path, "bad.3mf", b"junk")])
    assert w.banner.isVisible()
    assert "Not a valid .3mf file." in w.banner.label.text()
    assert w.banner.property("banner") == "danger"


def test_edit_hours_updates_price(qtbot, cfg_dir):
    w = make_window(qtbot)
    w.state.add_plate()
    card = w.plates_view.cards()[0]
    card.rows[0].grams_spin.setValue(50)
    before = w.summary.price_label.text()
    card.hours_spin.setValue(10)
    assert w.summary.price_label.text() != before
    assert w.state.job.plates[0].hours == 10
    assert w.plates_view.cards()[0] is card  # no rebuild while editing


def test_empty_state_text(qtbot, cfg_dir):
    w = make_window(qtbot)
    assert w.plates_view.empty_label.text() == "Drop a sliced .3mf or add a plate"
    assert not w.plates_view.empty_state.isHidden()


def test_wheel_ignored_without_focus(qtbot, cfg_dir):
    from pcc.gui.widgets.money_spin import MoneySpin
    qtbot.addWidget(s := MoneySpin("₱"))
    assert s.focusPolicy() == Qt.FocusPolicy.StrongFocus
