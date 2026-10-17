import pytest
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


# ---- fix round 1 ------------------------------------------------------
from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from pcc.core.models import FilamentUse  # noqa: E402


def _wheel(widget, delta=120):
    ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, delta),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                     Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, ev)
    return ev


def test_wheel_changes_only_when_focused(qtbot, cfg_dir):
    w = make_window(qtbot)
    w.state.add_plate()
    spin = w.plates_view.cards()[0].copies_spin
    spin.setValue(5)
    w.job_panel.customer_edit.setFocus()
    qtbot.waitUntil(lambda: not spin.hasFocus())
    ev = _wheel(spin)
    assert spin.value() == 5
    assert not ev.isAccepted()  # propagates to the scroll area
    spin.setFocus()
    qtbot.waitUntil(spin.hasFocus)
    _wheel(spin)
    assert spin.value() == 6


def test_rapid_edits_keep_widgets_and_focus(qtbot, cfg_dir, tmp_path):
    w = make_window(qtbot)
    w.import_files([_file(tmp_path)])
    cards = w.plates_view.cards()
    rows = [list(c.rows) for c in cards]
    card = cards[0]
    card.name_edit.selectAll()
    card.name_edit.setFocus()
    qtbot.waitUntil(card.name_edit.hasFocus)
    QTest.keyClicks(card.name_edit, "Benchy 12")
    assert card.name_edit.hasFocus()
    assert w.state.job.plates[0].name == "Benchy 12"
    for spin, text in ((card.rows[0].grams_spin, "12.5"), (card.hours_spin, "2")):
        spin.setFocus()
        qtbot.waitUntil(spin.hasFocus)
        spin.selectAll()
        QTest.keyClicks(spin, text)
        assert spin.hasFocus()
    assert w.state.job.plates[0].filaments[0].grams == 12.5
    assert w.plates_view.cards() == cards
    assert [list(c.rows) for c in w.plates_view.cards()] == rows


def test_new_job_confirmation(qtbot, cfg_dir, monkeypatch):
    w = make_window(qtbot)
    w.state.add_plate()
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.No)
    w.new_job()
    assert len(w.state.job.plates) == 1
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    w.new_job()
    assert w.state.job.plates == []
    assert w.plates_view.cards() == []


def test_new_job_without_plates_does_not_ask(qtbot, cfg_dir, monkeypatch):
    w = make_window(qtbot)

    def boom(*a, **k):
        raise AssertionError("should not ask")
    monkeypatch.setattr(QMessageBox, "question", boom)
    w.new_job()


def test_banner_levels_and_dismiss(qtbot, cfg_dir, tmp_path):
    w = make_window(qtbot)
    good, bad = _file(tmp_path), _file(tmp_path, "bad.3mf", b"junk")
    w.import_files([good, bad])
    assert w.banner.property("banner") == "warning"
    assert "bad.3mf: Not a valid .3mf file." in w.banner.label.text()
    w.import_files([bad])
    assert w.banner.property("banner") == "danger"
    qtbot.mouseClick(w.banner.dismiss_button, Qt.MouseButton.LeftButton)
    assert not w.banner.isVisible()
    w.import_files([bad])
    assert w.banner.isVisible()
    w.import_files([good])  # clean import hides the stale banner
    assert not w.banner.isVisible()


def test_import_merges_state_warnings_into_banner(qtbot, cfg_dir, tmp_path, monkeypatch):
    w = make_window(qtbot)
    orig = w.state.import_files

    def noisy(paths):
        w.state.warning.emit("heads up")
        return orig(paths)
    monkeypatch.setattr(w.state, "import_files", noisy)
    w.import_files([_file(tmp_path, "bad.3mf", b"junk"), _file(tmp_path)])
    text = w.banner.label.text()
    assert "heads up" in text and "bad.3mf" in text


def test_internal_fee_label_visibility(qtbot, cfg_dir):
    w = make_window(qtbot)
    w.state.add_plate()
    w.state.update_settings(hidden_plate_fee=0.0)
    assert w.summary.internal_fee_label.isHidden()
    w.state.update_settings(hidden_plate_fee=30.0)
    assert not w.summary.internal_fee_label.isHidden()
    assert w.summary.internal_fee_label.text().startswith("🔒 Internal fee")
    assert w.summary.internal_fee_label.toolTip() == "Not shown in exports"


def test_money_spin_symbol_follows_currency(qtbot, cfg_dir):
    w = make_window(qtbot)
    w.state.add_plate()
    w.state.update_settings(currency_code="EUR", currency_symbol="€")
    assert w.job_panel.packaging_spin.prefix().strip() == "€"
    assert w.plates_view.cards()[0].labor_spin.prefix().strip() == "€"


def test_add_and_remove_filament_row(qtbot, cfg_dir):
    w = make_window(qtbot)
    w.state.add_plate()
    card = w.plates_view.cards()[0]
    assert card.rows[0].remove_button.isHidden()  # last row cannot be removed
    qtbot.mouseClick(card.add_filament_button, Qt.MouseButton.LeftButton)
    assert len(w.state.job.plates[0].filaments) == 2
    assert len(card.rows) == 2 and w.plates_view.cards()[0] is card
    qtbot.mouseClick(card.rows[1].remove_button, Qt.MouseButton.LeftButton)
    assert len(w.state.job.plates[0].filaments) == 1
    assert len(card.rows) == 1


def test_missing_filament_falls_back_to_default(qtbot, cfg_dir):
    w = make_window(qtbot)
    w.state.add_plate()
    w.state.update_plate(w.state.job.plates[0].id,
                         filaments=[FilamentUse("does-not-exist", 5.0)])
    use = w.state.job.plates[0].filaments[0]
    assert use.filament_id == w.state.catalog.default_filament().id
    row = w.plates_view.cards()[0].rows[0]
    assert row.combo.currentData() == use.filament_id


@pytest.mark.filterwarnings("ignore:Function.*QDragEnterEvent:DeprecationWarning")
def test_drag_enter_filters_by_extension(qtbot, cfg_dir, tmp_path):
    from PySide6.QtGui import QDragEnterEvent
    w = make_window(qtbot)

    def enter(name):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(tmp_path / name))])
        ev = QDragEnterEvent(QPoint(5, 5), Qt.DropAction.CopyAction, mime,
                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        w.dragEnterEvent(ev)
        return ev.isAccepted()

    assert not enter("notes.txt")
    assert not w.drop_overlay.isVisible()
    assert enter("MODEL.3MF")
    assert w.drop_overlay.isVisible()
    w.dragLeaveEvent(None)
    assert not w.drop_overlay.isVisible()


def test_toast_sits_below_top_bar(qtbot, cfg_dir, tmp_path):
    w = make_window(qtbot)
    w.import_files([_file(tmp_path)])
    assert w.toast.isVisible()
    assert w.toast.y() >= w._wide.geometry().top()
    eb = w.summary.export_button
    export_rect = eb.rect().translated(eb.mapTo(w.centralWidget(), QPoint(0, 0)))
    assert not w.toast.geometry().intersects(export_rect)


def test_splash_uses_screen_device_pixel_ratio(qtbot, monkeypatch):
    from PySide6.QtGui import QGuiApplication

    from pcc.gui.splash import H, W, Splash

    class FakeScreen:
        def devicePixelRatio(self):
            return 1.5

    monkeypatch.setattr(QGuiApplication, "primaryScreen", staticmethod(lambda: FakeScreen()))
    s = Splash()
    qtbot.addWidget(s)
    pm = s.pixmap()
    assert pm.devicePixelRatio() == 1.5 and pm.width() == int(W * 1.5) and pm.height() == int(H * 1.5)
    monkeypatch.setattr(QGuiApplication, "primaryScreen", staticmethod(lambda: None))
    s2 = Splash()
    qtbot.addWidget(s2)
    assert s2.pixmap().devicePixelRatio() == 2.0
