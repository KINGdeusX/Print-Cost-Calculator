from pathlib import Path

import pytest
from PySide6.QtCore import QFile, QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDropEvent
from PySide6.QtWidgets import QInputDialog, QMessageBox

from pcc.core.currency import format_money
from pcc.core.pricing import compute_quote
from pcc.core.projects import ProjectConflictError, list_projects, load_project
from pcc.gui.main_window import MainWindow
from pcc.gui.state import AppState
from tests.fixtures.make3mf import MULTI_PLATE_PROJECT

SB = QMessageBox.StandardButton


def make(qtbot):
    state = AppState(legacy_paths=[])
    w = MainWindow(state)
    qtbot.addWidget(w)
    w.show()
    return state, w


def _file(tmp_path, name="Benchy.gcode.3mf"):
    f = tmp_path / name
    f.write_bytes(MULTI_PLATE_PROJECT)
    return f


def _dirty_editor(state, w, name="Proj"):
    state.new_project(name)
    w.show_editor()
    state.add_plate()
    assert state.dirty
    return state.project_path


def _drop(w, path):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    w.dropEvent(QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))


def test_starts_on_projects_page(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    assert w.stack.currentWidget() is w.projects_page
    assert w.windowTitle() == "Print Cost Calculator"
    assert w.projects_page.empty_label.isVisible()
    assert w.projects_page.empty_label.text() == \
        "No projects yet — drop a sliced .3mf here or click ➕ New"
    assert w.projects_page.new_button.text() == "➕ New"
    assert w.projects_page.import_button.text() == "📂 Import .3mf"


def test_drop_on_list_creates_and_opens_first(qtbot, cfg_dir, data_dir, tmp_path):
    state, w = make(qtbot)
    _drop(w, _file(tmp_path))
    assert w.stack.currentWidget() is w.editor_page
    assert state.project.name == "Benchy"
    assert len(state.job.plates) == 2
    assert len(list_projects()[0]) == 1


def test_drop_failure_stays_on_list_with_banner(qtbot, cfg_dir, data_dir, tmp_path):
    state, w = make(qtbot)
    bad = tmp_path / "bad.3mf"
    bad.write_bytes(b"junk")
    _drop(w, bad)
    assert w.stack.currentWidget() is w.projects_page
    assert w.banner.isVisible() and "bad.3mf" in w.banner.label.text()


def test_new_button_creates_and_opens(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    w.projects_page.new_button.click()
    assert w.stack.currentWidget() is w.editor_page
    assert state.project.name == "Untitled project"
    assert w.header.name_edit.text() == "Untitled project"
    assert w.windowTitle() == "Untitled project — Print Cost Calculator"


def test_open_from_list_double_click(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    path = state.new_project("Opened")
    state.close_project()
    w.show_projects()
    item = w.projects_page.list_widget.item(0)
    w.projects_page.list_widget.itemActivated.emit(item)
    assert w.stack.currentWidget() is w.editor_page
    assert state.project_path == path


@pytest.mark.parametrize("choice", [SB.Save, SB.Discard, SB.Cancel])
def test_back_prompt_save_dont_cancel(qtbot, cfg_dir, data_dir, monkeypatch, choice):
    state, w = make(qtbot)
    path = _dirty_editor(state, w)
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda parent, title, text, *a, **k: asked.append(text) or choice)
    w.header.back_button.click()
    assert asked == ["Save changes to 'Proj'?"]
    on_disk = len(load_project(path).job.plates)
    if choice == SB.Cancel:
        assert w.stack.currentWidget() is w.editor_page
        assert state.dirty and state.project is not None
        assert on_disk == 0
    else:
        assert w.stack.currentWidget() is w.projects_page
        assert state.project is None
        assert on_disk == (1 if choice == SB.Save else 0)
        assert w.projects_page.list_widget.count() == 1
    if choice == SB.Save:
        item = w.projects_page.list_widget.item(0)
        assert item.data(Qt.ItemDataRole.UserRole) == path


def test_back_clean_does_not_prompt(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    state.new_project("C")
    w.show_editor()
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("asked")))
    w.header.back_button.click()
    assert w.stack.currentWidget() is w.projects_page


def test_close_prompt_cancel_keeps_window(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    _dirty_editor(state, w)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: SB.Cancel)
    ev = QCloseEvent()
    w.closeEvent(ev)
    assert not ev.isAccepted()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: SB.Discard)
    ev = QCloseEvent()
    w.closeEvent(ev)
    assert ev.isAccepted()


def test_ctrl_n_prompts_when_dirty(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    first = _dirty_editor(state, w, "First")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: SB.Cancel)
    w.new_project_flow()
    assert state.project_path == first and state.dirty
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: SB.Save)
    w.new_project_flow()
    assert state.project_path != first and state.project.name == "Untitled project"
    assert len(load_project(first).job.plates) == 1
    assert w.stack.currentWidget() is w.editor_page


def _overwrite_dialog(monkeypatch, label):
    texts = []

    def fake_exec(self):
        texts.append(self.text())
        self._pick = next(b for b in self.buttons() if b.text() == label)
        return 0
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: self._pick)
    return texts


@pytest.mark.parametrize("label,saved", [("Overwrite", True), ("Cancel", False)])
def test_conflict_dialog_overwrite(qtbot, cfg_dir, data_dir, monkeypatch, label, saved):
    from pcc.core import projects as core
    state, w = make(qtbot)
    path = _dirty_editor(state, w)
    core.rename_project(path, "Elsewhere")  # bumps updated_at behind our back
    with pytest.raises(ProjectConflictError):
        state.save_project()
    texts = _overwrite_dialog(monkeypatch, label)
    assert w.save_current() is saved
    assert texts == ["This project was changed elsewhere (another window?). "
                     "Overwrite it with your version?"]
    assert state.dirty is (not saved)
    assert len(load_project(path).job.plates) == (1 if saved else 0)


def test_save_oserror_shows_critical_and_stays_dirty(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    _dirty_editor(state, w)

    def boom(force=False):
        raise PermissionError("disk locked")
    shown = []
    monkeypatch.setattr(state, "save_project", boom)
    monkeypatch.setattr(QMessageBox, "critical",
                        lambda parent, title, text, *a: shown.append(text))
    assert w.save_current() is False
    assert state.dirty and "disk locked" in shown[0]


def test_search_filters_name_and_customer(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    state.new_project("Alpha")
    state.update_job(customer="Zed Corp")
    state.save_project()
    state.new_project("Beta")
    state.save_project()
    state.close_project()
    page = w.projects_page
    page.refresh()
    assert page.list_widget.count() == 2
    page.search_edit.setText("zed")
    visible = [i for i in range(2) if not page.list_widget.item(i).isHidden()]
    assert len(visible) == 1
    page.search_edit.setText("BET")
    visible = [i for i in range(2) if not page.list_widget.item(i).isHidden()]
    assert len(visible) == 1
    page.search_edit.setText("")
    assert not any(page.list_widget.item(i).isHidden() for i in range(2))


def test_delete_moves_to_trash(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    path = state.new_project("Gone")
    state.close_project()
    page = w.projects_page
    page.refresh()
    asked, trashed = [], []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda parent, title, text, *a, **k: asked.append(text) or SB.Yes)
    monkeypatch.setattr(QFile, "moveToTrash",
                        staticmethod(lambda p: trashed.append(p) or __import__("shutil").rmtree(p) or True))
    page.delete_project(path)
    assert asked == ["Delete 'Gone'? It will be moved to the Recycle Bin."]
    assert trashed == [str(path)]
    assert page.list_widget.count() == 0
    assert page.empty_label.isVisible()


def test_delete_declined_keeps_project(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    path = state.new_project("Keep")
    state.close_project()
    w.projects_page.refresh()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: SB.No)
    w.projects_page.delete_project(path)
    assert path.exists() and w.projects_page.list_widget.count() == 1


def test_delete_falls_back_to_permanent(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    path = state.new_project("Hard")
    state.close_project()
    w.projects_page.refresh()
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda parent, title, text, *a, **k: asked.append(text) or SB.Yes)
    monkeypatch.setattr(QFile, "moveToTrash", staticmethod(lambda p: False))
    w.projects_page.delete_project(path)
    assert len(asked) == 2 and "permanently" in asked[1].lower()
    assert not path.exists() and w.projects_page.list_widget.count() == 0


def test_rename_and_duplicate_from_menu(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    path = state.new_project("Old")
    state.close_project()
    page = w.projects_page
    page.refresh()
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Fresh", True))
    page.rename_project(path)
    assert load_project(path).name == "Fresh"
    page.duplicate_project(path)
    names = sorted(h.project.name for h in list_projects()[0])
    assert names == ["Fresh", "Fresh (copy)"]
    assert page.list_widget.count() == 2


def test_rename_open_project_keeps_state_in_sync(qtbot, cfg_dir, data_dir, monkeypatch):
    state, w = make(qtbot)
    path = state.new_project("Old")
    w.projects_page.refresh()
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("New", True))
    w.projects_page.rename_project(path)
    assert state.project.name == "New"
    assert w.header.name_edit.text() == "New"


def test_dirty_indicator_and_save_button(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    state.new_project("D")
    w.show_editor()
    h = w.header
    assert h.save_button.text() == "💾 Save" and h.back_button.text() == "⬅ Back"
    assert not h.save_button.isEnabled() and not h.dirty_label.isVisible()
    assert w.windowTitle() == "D — Print Cost Calculator"
    state.add_plate()
    assert h.save_button.isEnabled() and h.dirty_label.isVisible()
    assert h.dirty_label.text() == "● Unsaved changes"
    assert w.windowTitle() == "D • — Print Cost Calculator" or w.windowTitle().startswith("D •")
    h.save_button.click()
    assert not state.dirty and not h.save_button.isEnabled()
    assert not h.dirty_label.isVisible()


def test_header_rename_marks_dirty(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    state.new_project("D")
    w.show_editor()
    w.header.name_edit.setText("Renamed")
    w.header.name_edit.editingFinished.emit()
    assert state.project.name == "Renamed" and state.dirty
    assert w.windowTitle().startswith("Renamed")


def test_printer_combo_lives_in_editor(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    assert w.editor_page.isAncestorOf(w.printer_combo)
    assert not w.editor_page.isAncestorOf(w.currency_combo)


def test_list_price_matches_quote(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    state.new_project("Priced")
    state.add_plate()
    state.update_plate(state.job.plates[0].id, hours=2.0)
    state.save_project()
    expected = format_money(compute_quote(state.job, state.settings, state.catalog).price,
                            state.settings.currency_symbol)
    state.close_project()
    page = w.projects_page
    page.refresh()
    row = page.list_widget.itemWidget(page.list_widget.item(0))
    assert expected in row.price_label.text()
    assert row.plates_label.text() == "1 plates" or row.plates_label.text() == "1 plate"


def test_unpriceable_project_shows_dash(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    state.new_project("Empty")
    state.close_project()
    page = w.projects_page
    page.refresh()
    row = page.list_widget.itemWidget(page.list_widget.item(0))
    assert row.price_label.text() == "—"
    assert row.customer_label.text() == "—"
    assert row.plates_label.text() == "0 plates"


def test_row_uses_plate_thumbnail(qtbot, cfg_dir, data_dir, tmp_path):
    state, w = make(qtbot)
    created, _ = state.create_projects_from_files([_file(tmp_path)])
    page = w.projects_page
    page.refresh()
    row = page.list_widget.itemWidget(page.list_widget.item(0))
    assert row.has_thumbnail


def test_damaged_project_warning_in_banner(qtbot, cfg_dir, data_dir):
    state, w = make(qtbot)
    bad = data_dir / "Projects" / "broken"
    bad.mkdir(parents=True)
    (bad / "project.json").write_text("{nope", encoding="utf-8")
    w.show_projects()
    assert w.banner.isVisible() and "broken" in w.banner.label.text()


def test_import_dialog_in_list_creates_projects(qtbot, cfg_dir, data_dir, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    state, w = make(qtbot)
    f = _file(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a, **k: ([str(f)], ""))
    w.projects_page.import_button.click()
    assert w.stack.currentWidget() is w.editor_page and state.project.name == "Benchy"


def test_pricing_error_shows_dash(qtbot, cfg_dir, data_dir, monkeypatch):
    from pcc.core.pricing import PricingError
    from pcc.gui.widgets import projects_page as pp
    state, w = make(qtbot)
    state.new_project("Bad")
    state.add_plate()
    state.save_project()
    state.close_project()

    def boom(*a):
        raise PricingError("nope")
    monkeypatch.setattr(pp, "compute_quote", boom)
    w.projects_page.refresh()
    row = w.projects_page.list_widget.itemWidget(w.projects_page.list_widget.item(0))
    assert row.price_label.text() == "—"
