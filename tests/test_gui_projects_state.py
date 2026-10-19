import pytest

from pcc.core.models import Catalog
from pcc.core.projects import InvoiceRecord, ProjectConflictError, load_project
from pcc.gui.state import AppState
from tests.fixtures.make3mf import MULTI_PLATE_PROJECT


def test_new_open_edit_save_cycle(qtbot, cfg_dir, data_dir):
    s = AppState(legacy_paths=[])
    path = s.new_project("P1")
    assert s.project.name == "P1" and not s.dirty and s.project_path == path
    with qtbot.waitSignal(s.dirty_changed):
        s.add_plate()
    assert s.dirty
    s.save_project()
    assert not s.dirty
    with qtbot.waitSignal(s.project_closed):
        s.close_project()
    assert s.project is None and s.project_path is None and s.job.plates == []
    with qtbot.waitSignal(s.project_opened):
        s.open_project(path)
    assert len(s.job.plates) == 1 and not s.dirty


def test_dirty_changed_only_on_transitions(qtbot, cfg_dir, data_dir):
    s = AppState(legacy_paths=[])
    s.new_project()
    seen = []
    s.dirty_changed.connect(seen.append)
    s.add_plate()
    s.add_plate()
    s.save_project()
    assert seen == [True, False]


def test_settings_change_not_dirty(qtbot, cfg_dir, data_dir):
    s = AppState(legacy_paths=[])
    s.new_project()
    s.update_settings(margin_pct=70)
    assert not s.dirty


def test_open_repairs_deleted_profiles_and_marks_dirty(qtbot, cfg_dir, data_dir):
    s = AppState(legacy_paths=[])
    path = s.new_project("R")
    s.update_job(printer_id="bambu-p1s")
    s.save_project()
    s.close_project()
    cat = Catalog(printers=[p for p in s.catalog.printers if p.id != "bambu-p1s"],
                  filaments=s.catalog.filaments)
    s.set_catalog(cat)
    warnings = []
    s.warning.connect(warnings.append)
    s.open_project(path)
    assert s.job.printer_id == cat.default_printer().id
    assert warnings == ["Some items used a deleted profile and were switched to the default."]
    assert s.dirty


def test_conflict_propagates_and_force(qtbot, cfg_dir, data_dir):
    a = AppState(legacy_paths=[])
    path = a.new_project("C")
    b = AppState(legacy_paths=[])
    b.open_project(path)
    b.add_plate()
    b.save_project()
    a.add_plate()
    with pytest.raises(ProjectConflictError):
        a.save_project()
    assert a.dirty
    a.save_project(force=True)
    assert not a.dirty


def test_create_projects_from_files(qtbot, cfg_dir, data_dir, tmp_path):
    s = AppState(legacy_paths=[])
    good = tmp_path / "Cube.GCODE.3MF"
    good.write_bytes(MULTI_PLATE_PROJECT)
    bad = tmp_path / "x.3mf"
    bad.write_bytes(b"no")
    n = []
    s.projects_changed.connect(lambda: n.append(1))
    created, failures = s.create_projects_from_files([good, bad])
    assert len(created) == 1 and failures == [("x.3mf", "Not a valid .3mf file.")]
    assert load_project(created[0]).name == "Cube"
    assert len(load_project(created[0]).job.plates) == 2
    assert n == [1] and s.project is None and s.job.plates == []


def test_create_from_files_keeps_open_project(qtbot, cfg_dir, data_dir, tmp_path):
    s = AppState(legacy_paths=[])
    path = s.new_project("Open")
    s.add_plate()
    good = tmp_path / "a.3mf"
    good.write_bytes(MULTI_PLATE_PROJECT)
    s.create_projects_from_files([good])
    assert s.project_path == path and len(s.job.plates) == 1 and s.dirty


def test_record_invoice_saves(qtbot, cfg_dir, data_dir):
    s = AppState(legacy_paths=[])
    path = s.new_project("I")
    s.add_plate()
    rec = InvoiceRecord("INV-0001", "2026-10-19", "Ana", 100.0, "$", "f.pdf")
    s.record_invoice(rec)
    assert not s.dirty
    assert load_project(path).invoices == [rec]


def test_rename_marks_dirty(qtbot, cfg_dir, data_dir):
    s = AppState(legacy_paths=[])
    s.new_project("Old")
    s.rename_current("New")
    assert s.dirty and s.project.name == "New"
    s.save_project()
    assert load_project(s.project_path).name == "New"


def test_record_invoice_save_failure_keeps_record_and_dirty(qtbot, cfg_dir, data_dir, monkeypatch):
    from pcc.gui import state as state_mod
    s = AppState(legacy_paths=[])
    path = s.new_project("I")
    real = state_mod.save_project

    def boom(*a, **k):
        raise ProjectConflictError("x")

    monkeypatch.setattr(state_mod, "save_project", boom)
    rec = InvoiceRecord("INV-0001", "2026-10-19", "Ana", 100.0, "$", "f.pdf")
    with pytest.raises(ProjectConflictError):
        s.record_invoice(rec)
    assert s.dirty and s.project.invoices == [rec]
    monkeypatch.setattr(state_mod, "save_project", real)
    s.save_project(force=True)
    assert load_project(path).invoices == [rec] and not s.dirty


def test_rename_strips_ignores_empty_and_signals(qtbot, cfg_dir, data_dir):
    s = AppState(legacy_paths=[])
    s.new_project("Old")
    s.rename_current("   ")
    assert s.project.name == "Old" and not s.dirty
    with qtbot.waitSignal(s.project_renamed) as sig:
        s.rename_current("  New  ")
    assert sig.args == ["New"] and s.project.name == "New"


def test_create_from_files_per_file_save_failure(qtbot, cfg_dir, data_dir, tmp_path, monkeypatch):
    from pcc.gui import state as state_mod
    real = state_mod.create_project
    calls = []

    def flaky(name, job, root=None):
        calls.append(name)
        if len(calls) == 1:
            raise OSError("disk full")
        return real(name, job, root)

    monkeypatch.setattr(state_mod, "create_project", flaky)
    a, b = tmp_path / "a.3mf", tmp_path / "b.3mf"
    a.write_bytes(MULTI_PLATE_PROJECT)
    b.write_bytes(MULTI_PLATE_PROJECT)
    s = AppState(legacy_paths=[])
    n = []
    s.projects_changed.connect(lambda: n.append(1))
    created, failures = s.create_projects_from_files([a, b])
    assert len(created) == 1 and n == [1]
    assert failures == [("a.3mf", "Could not save project: disk full")]


def test_open_corrupt_project_leaves_state(qtbot, cfg_dir, data_dir):
    from pcc.core.projects import ProjectError
    s = AppState(legacy_paths=[])
    good = s.new_project("G")
    s.add_plate()
    bad = s.new_project("B")
    (bad / "project.json").write_text("{nope")
    s.open_project(good)
    s.add_plate()
    project, job = s.project, s.job
    with pytest.raises(ProjectError):
        s.open_project(bad)
    assert s.project is project and s.job is job and s.dirty
    assert s.project_path == good


def test_save_oserror_keeps_dirty_and_project(qtbot, cfg_dir, data_dir, monkeypatch):
    from pcc.gui import state as state_mod
    s = AppState(legacy_paths=[])
    s.new_project("S")
    s.add_plate()
    project = s.project

    def boom(*a, **k):
        raise OSError("locked")

    monkeypatch.setattr(state_mod, "save_project", boom)
    with pytest.raises(OSError):
        s.save_project()
    assert s.dirty and s.project is project
