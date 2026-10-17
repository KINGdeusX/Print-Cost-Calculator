import pytest

from pcc.core.models import Filament, FilamentUse
from pcc.gui.state import AppState
from tests.fixtures.make3mf import MULTI_PLATE_PROJECT


def test_add_plate_emits_quote(qtbot, cfg_dir):
    s = AppState(legacy_paths=[])
    with qtbot.waitSignal(s.quote_changed):
        p = s.add_plate()
    assert len(s.job.plates) == 1
    assert p.name == "Plate 1" and len(p.filaments) == 1


def test_empty_job_has_no_quote_and_no_error(qtbot, cfg_dir):
    s = AppState(legacy_paths=[])
    assert s.quote is None and s.last_error is None


def test_settings_debounced_save(qtbot, cfg_dir):
    s = AppState(legacy_paths=[])
    s.update_settings(margin_pct=65)
    qtbot.waitUntil(lambda: (cfg_dir / "settings.json").exists(), timeout=2000)
    assert AppState(legacy_paths=[]).settings.margin_pct == 65


def test_flush_saves_immediately(qtbot, cfg_dir, tmp_path):
    d = tmp_path / "other"
    s = AppState(directory=d, legacy_paths=[])
    s.update_settings(margin_pct=70)
    s.flush()
    assert (d / "settings.json").exists() and (d / "catalog.json").exists()


def test_unknown_settings_field(qtbot, cfg_dir):
    s = AppState(legacy_paths=[])
    with pytest.raises(ValueError):
        s.update_settings(bogus=1)


def test_import_files(qtbot, cfg_dir, tmp_path):
    good = tmp_path / "a.3mf"
    good.write_bytes(MULTI_PLATE_PROJECT)
    bad = tmp_path / "bad.3mf"
    bad.write_bytes(b"nope")
    s = AppState(legacy_paths=[])
    with qtbot.waitSignal(s.job_changed):
        failures = s.import_files([good, bad, tmp_path / "missing.3mf"])
    assert len(s.job.plates) == 2
    assert [f[0] for f in failures] == ["bad.3mf", "missing.3mf"]
    assert failures[0][1] == "Not a valid .3mf file."
    assert failures[1][1] == "Could not read file."
    assert "P1S" in s.catalog.printer(s.job.printer_id).name
    assert s.settings.last_printer_id == s.job.printer_id
    assert s.quote is not None
    s.import_files([good])
    assert len(s.job.plates) == 4


def test_deleted_filament_falls_back(qtbot, cfg_dir):
    s = AppState(legacy_paths=[])
    extra = Filament(id="x", name="X", type="PLA", price_per_kg=1.0)
    s.catalog.filaments.append(extra)
    p = s.add_plate()
    s.update_plate(p.id, filaments=[FilamentUse("x", 10)])
    from copy import deepcopy
    cat = deepcopy(s.catalog)
    cat.filaments = [f for f in cat.filaments if f.id != "x"]
    with qtbot.waitSignal(s.warning) as sig:
        s.set_catalog(cat)
    assert "deleted profile" in sig.args[0]
    assert s.job.plates[0].filaments[0].filament_id == cat.default_filament().id


def test_pricing_error_sets_last_error(qtbot, cfg_dir):
    s = AppState(legacy_paths=[])
    p = s.add_plate()
    s.update_plate(p.id, copies=0)
    assert s.quote is None and s.last_error
    with pytest.raises(ValueError):
        s.update_plate("nope", hours=1)


def test_update_job_printer_sets_last(qtbot, cfg_dir):
    s = AppState(legacy_paths=[])
    pid = s.catalog.printers[-1].id
    s.update_job(printer_id=pid, customer="Niño")
    assert s.settings.last_printer_id == pid and s.job.customer == "Niño"
    s.new_job()
    assert s.job.printer_id == pid and s.job.plates == []
