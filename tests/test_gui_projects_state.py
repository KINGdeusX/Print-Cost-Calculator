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


def test_new_job_still_works(qtbot, cfg_dir, data_dir):
    s = AppState(legacy_paths=[])
    s.add_plate()
    s.new_job()
    assert s.job.plates == []
