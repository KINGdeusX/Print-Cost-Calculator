"""Projects list: row interaction (mouse, context menu, keys) and refresh policy."""
from PySide6.QtCore import QFile, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from pcc.core.projects import list_projects, load_project
from pcc.gui.main_window import MainWindow
from pcc.gui.state import AppState
from pcc.gui.widgets import projects_page as page_mod

SB = QMessageBox.StandardButton
MENU_TEXTS = ["Rename…", "Duplicate", "Show in folder", "", "Delete…"]


def make(qtbot):
    state = AppState(legacy_paths=[])
    w = MainWindow(state)
    qtbot.addWidget(w)
    w.show()
    return state, w


def _one_project(qtbot, name="Row"):
    state, w = make(qtbot)
    path = state.new_project(name)
    state.close_project()  # back on the list -> refreshed
    assert QTest.qWaitForWindowExposed(w)
    page = w.projects_page
    item = page.list_widget.item(0)
    return state, w, page, item, page.list_widget.itemWidget(item), path


def test_more_button_is_hit_by_real_clicks(qtbot, cfg_dir, data_dir):
    state, w, page, item, row, path = _one_project(qtbot)
    btn = row.more_button
    # the same hit-testing the window uses to deliver real mouse events
    centre = btn.mapToGlobal(btn.rect().center())
    assert w.childAt(w.mapFromGlobal(centre)) is btn
    seen = []

    def close_popup():
        popup = QApplication.activePopupWidget()
        seen.append([a.text() for a in popup.actions()] if popup else None)
        if popup:
            popup.close()

    QTimer.singleShot(50, close_popup)
    QTest.mouseClick(btn, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: bool(seen), timeout=2000)
    assert seen == [MENU_TEXTS]


def test_double_click_on_row_name_still_opens(qtbot, cfg_dir, data_dir):
    state, w, page, item, row, path = _one_project(qtbot)
    QTest.mouseClick(row.name_label, Qt.MouseButton.LeftButton)  # sets the pressed row
    QTest.mouseDClick(row.name_label, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: w.stack.currentWidget() is w.editor_page, timeout=2000)
    assert state.project_path == path


def _fake_exec(pick, seen):
    def fake(page, menu, pos):
        acts = menu.actions()
        seen.append([x.text() for x in acts])
        act = next(x for x in acts if x.text() == pick)
        act.trigger()
        return act
    return fake


def test_right_click_context_menu_actions(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w, page, item, row, path = _one_project(qtbot, "Ctx")
    lw = page.list_widget
    assert lw.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
    seen = []
    monkeypatch.setattr(page_mod.ProjectsPage, "_popup", _fake_exec("Rename…", seen))
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Renamed", True))
    lw.customContextMenuRequested.emit(lw.visualItemRect(item).center())
    assert seen == [MENU_TEXTS]
    assert load_project(path).name == "Renamed"
    # off-row right-click shows nothing
    seen.clear()
    lw.customContextMenuRequested.emit(lw.viewport().rect().bottomRight())
    assert seen == []


def test_context_menu_duplicate(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w, page, item, row, path = _one_project(qtbot, "Dup")
    lw = page.list_widget
    monkeypatch.setattr(page_mod.ProjectsPage, "_popup", _fake_exec("Duplicate", []))
    lw.customContextMenuRequested.emit(lw.visualItemRect(item).center())
    assert sorted(h.project.name for h in list_projects()[0]) == ["Dup", "Dup (copy)"]


def test_f2_renames_current_row(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w, page, item, row, path = _one_project(qtbot, "Key")
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("ByKey", True))
    page.list_widget.setCurrentItem(item)
    QTest.keyClick(page.list_widget, Qt.Key.Key_F2)
    assert load_project(path).name == "ByKey"


def test_delete_key_deletes_with_confirmation(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w, page, item, row, path = _one_project(qtbot, "Del")
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda parent, title, text, *a, **k: asked.append(text) or SB.Yes)
    monkeypatch.setattr(QFile, "moveToTrash", staticmethod(
        lambda p: __import__("shutil").rmtree(p) or True))
    page.list_widget.setCurrentItem(item)
    QTest.keyClick(page.list_widget, Qt.Key.Key_Delete)
    assert asked == ["Delete 'Del'? It will be moved to the Recycle Bin."]
    assert not path.exists() and page.list_widget.count() == 0


def test_delete_key_declined_keeps(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w, page, item, row, path = _one_project(qtbot, "Stay")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: SB.No)
    page.list_widget.setCurrentItem(item)
    QTest.keyClick(page.list_widget, Qt.Key.Key_Delete)
    assert path.exists() and page.list_widget.count() == 1


def test_keys_without_current_row_do_nothing(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    called = []
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: called.append(1) or ("", False))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: called.append(2) or SB.No)
    QTest.keyClick(w.projects_page.list_widget, Qt.Key.Key_F2)
    QTest.keyClick(w.projects_page.list_widget, Qt.Key.Key_Delete)
    assert called == []


# -- data folder that cannot be created (item 2) -----------------------------
import os  # noqa: E402
import sys  # noqa: E402

import pytest  # noqa: E402

needs_posix_perms = pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="needs POSIX permissions and a non-root user")


@pytest.fixture
def readonly_data_dir(tmp_path, monkeypatch):
    parent = tmp_path / "ro"
    parent.mkdir()
    parent.chmod(0o555)
    monkeypatch.setenv("PCC_DATA_DIR", str(parent / "data"))
    yield parent / "data"
    parent.chmod(0o755)


@needs_posix_perms
def test_list_projects_reports_unavailable_folder(readonly_data_dir):
    handles, warnings = list_projects()
    assert handles == []
    assert len(warnings) == 1 and warnings[0].startswith("Projects folder unavailable: ")


@needs_posix_perms
def test_app_starts_without_data_folder(qtbot, cfg_dir, readonly_data_dir, monkeypatch):
    from pcc.gui.dialogs.settings_dialog import SettingsDialog

    state, w = make(qtbot)
    assert w.stack.currentWidget() is w.projects_page
    assert w.banner.isVisible()
    assert "Projects folder unavailable" in w.banner.label.text()
    d = SettingsDialog(state, w)
    qtbot.addWidget(d)
    assert d.data_folder_label.text() == str(readonly_data_dir / "Projects")
    opened = []
    from pcc.gui.dialogs import settings_dialog
    monkeypatch.setattr(settings_dialog.QDesktopServices, "openUrl",
                        lambda url: opened.append(url) or True)
    d.open_data_folder_button.click()  # must not raise
    assert len(opened) == 1
    assert not readonly_data_dir.exists()


# -- refresh policy (item 4) -------------------------------------------------
class _Calls(list):
    thumbs: list


@pytest.fixture
def scans(monkeypatch):
    calls = _Calls()
    real = page_mod.list_projects

    def spy(*a, **k):
        calls.append(1)
        return real(*a, **k)
    monkeypatch.setattr(page_mod, "list_projects", spy)
    thumbs = []
    real_thumb = page_mod._first_thumbnail
    monkeypatch.setattr(page_mod, "_first_thumbnail",
                        lambda h: thumbs.append(1) or real_thumb(h))
    calls.thumbs = thumbs
    return calls


def test_startup_scans_once(qtbot, cfg_dir, data_dir, scans):
    make(qtbot)
    assert len(scans) == 1


def test_hidden_list_is_not_rescanned(qtbot, cfg_dir, data_dir, scans):
    state, w = make(qtbot)
    state.new_project("Edit")
    state.add_plate()
    scans.clear()
    state.update_settings(margin_pct=state.settings.margin_pct + 5)
    state.set_catalog(state.catalog)
    state.save_project()  # projects_changed while the editor is shown
    assert scans == []
    w.go_back()
    assert w.stack.currentWidget() is w.projects_page
    assert len(scans) == 1


def test_visible_list_reprices_without_disk_read(qtbot, cfg_dir, data_dir, scans):
    from pcc.core.currency import format_money
    from pcc.core.pricing import compute_quote

    state, w = make(qtbot)
    state.new_project("Priced")
    state.add_plate()
    state.update_plate(state.job.plates[0].id, hours=2.0)
    state.save_project()
    w.go_back()
    row = w.projects_page.list_widget.itemWidget(w.projects_page.list_widget.item(0))
    del scans[:]
    scans.thumbs.clear()
    state.update_settings(margin_pct=state.settings.margin_pct + 25)
    state.set_catalog(state.catalog)
    assert scans == [] and scans.thumbs == []
    job = load_project(list_projects()[0][0].path).job
    want = format_money(compute_quote(job, state.settings, state.catalog).price,
                        state.settings.currency_symbol)
    assert row.price_label.text() == want


def test_list_page_actions_rescan(qtbot, cfg_dir, data_dir, scans, monkeypatch):
    state, w = make(qtbot)
    path = state.new_project("Act")
    state.close_project()
    del scans[:]
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Act2", True))
    w.projects_page.rename_project(path)
    assert len(scans) == 1
    w.projects_page.duplicate_project(path)
    assert len(scans) == 2 and w.projects_page.list_widget.count() == 2
