import json

from pcc.core.storage import (
    atomic_write_text, config_dir, default_catalog, default_settings,
    load_state, save_catalog, save_settings,
)


def test_config_dir_env(cfg_dir):
    assert config_dir() == cfg_dir


def test_first_run_defaults(cfg_dir):
    r = load_state(legacy_paths=[])
    assert r.settings.currency_symbol == "₱"
    assert r.catalog.default_filament().type == "PLA"
    assert {p.name for p in r.catalog.printers} >= {"Bambu Lab P1S", "Bambu Lab H2D Pro"}
    assert r.warnings == []


def test_seed_catalog_shape():
    c = default_catalog()
    assert len(c.printers) == 15
    assert c.printer("custom").watts == 150 and c.printer("custom").name == "Custom FDM"
    assert c.printer("bambu-x1-carbon").model_match == ["X1 Carbon", "X1C"]
    ids = [p.id for p in c.printers]
    assert ids.index("bambu-a1-mini") < ids.index("bambu-a1")
    assert ids.index("bambu-x1-carbon") < ids.index("bambu-x1")
    assert ids.index("bambu-x1e") < ids.index("bambu-x1")
    assert ids.index("bambu-h2d-pro") < ids.index("bambu-h2d")
    assert [f.id for f in c.filaments] == ["pla", "petg", "abs", "asa", "tpu", "pla-cf"]
    assert c.filament("pla").is_default and c.filament("pla").name == "Generic PLA"
    assert c.filament("pla-cf").price_per_kg == 1200.0
    assert c.filament("tpu").price_per_kg == 1000.0


def test_round_trip(cfg_dir):
    r = load_state(legacy_paths=[])
    r.settings.margin_pct = 65
    r.catalog.filaments.append(
        type(r.catalog.filaments[0])(id="x", name="Silk", type="PLA", price_per_kg=999.0)
    )
    save_settings(r.settings)
    save_catalog(r.catalog)
    r2 = load_state(legacy_paths=[])
    assert r2.settings == r.settings and r2.catalog == r.catalog


def test_corrupt_settings_backed_up(cfg_dir):
    cfg_dir.mkdir()
    (cfg_dir / "settings.json").write_text("{")
    r = load_state(legacy_paths=[])
    assert r.settings == default_settings()
    assert len(list(cfg_dir.glob("settings.json.bak-*"))) == 1
    assert r.warnings == [
        "settings.json was unreadable; a backup was saved and defaults loaded."
    ]


def test_malformed_entry_treated_as_corrupt(cfg_dir):
    cfg_dir.mkdir()
    (cfg_dir / "catalog.json").write_text(json.dumps({"printers": [{"name": "x"}]}))
    r = load_state(legacy_paths=[])
    assert len(list(cfg_dir.glob("catalog.json.bak-*"))) == 1
    assert r.catalog.printer("custom") is not None
    assert r.warnings == [
        "catalog.json was unreadable; a backup was saved and defaults loaded."
    ]


def test_non_object_json_is_corrupt(cfg_dir):
    cfg_dir.mkdir()
    (cfg_dir / "settings.json").write_text("[]")
    r = load_state(legacy_paths=[])
    assert len(list(cfg_dir.glob("settings.json.bak-*"))) == 1
    assert len(r.warnings) == 1


def test_migrate_v01(cfg_dir, tmp_path):
    legacy = tmp_path / "pricing_config.json"
    legacy.write_text(json.dumps(
        {"filament_cost": 900, "packaging": 15, "rate": 11, "power": 200, "margin": 40}
    ))
    r = load_state(legacy_paths=[legacy])
    assert r.warnings == ["Imported settings from v0.1"]
    assert r.settings.default_packaging == 15
    assert r.settings.electricity_rate == 11
    assert r.settings.margin_pct == 40
    assert r.catalog.printers[0].id == "my-printer"
    assert r.catalog.printers[0].watts == 200
    assert r.settings.last_printer_id == "my-printer"
    assert r.catalog.default_filament().price_per_kg == 900
    assert r.catalog.filament("pla-cf").price_per_kg == 1350
    assert (cfg_dir / "settings.json").exists() and (cfg_dir / "catalog.json").exists()
    r2 = load_state(legacy_paths=[legacy])
    assert r2.warnings == [] and r2.catalog.printers[0].id == "my-printer"


def test_migrate_ignores_non_numeric_values(cfg_dir, tmp_path):
    legacy = tmp_path / "pricing_config.json"
    legacy.write_text(json.dumps({"margin": "lots", "rate": 9, "power": None}))
    r = load_state(legacy_paths=[legacy])
    assert r.settings.margin_pct == 50 and r.settings.electricity_rate == 9
    assert r.catalog.printers[0].id != "my-printer"


def test_migrate_empty_legacy_file(cfg_dir, tmp_path):
    legacy = tmp_path / "pricing_config.json"
    legacy.write_text("")
    r = load_state(legacy_paths=[legacy])
    assert r.settings.margin_pct == 50 and r.warnings == []


def test_migrate_invalid_or_non_object_legacy(cfg_dir, tmp_path):
    for text in ("{", "[1]"):
        legacy = tmp_path / "pricing_config.json"
        legacy.write_text(text)
        r = load_state(legacy_paths=[legacy])
        assert r.warnings == [] and r.settings.margin_pct == 50


def test_atomic_write_leaves_no_temp(cfg_dir):
    target = cfg_dir / "sub" / "a.txt"
    atomic_write_text(target, "héllo")
    assert target.read_text(encoding="utf-8") == "héllo"
    assert [p.name for p in target.parent.iterdir()] == ["a.txt"]


def test_missing_filaments_filled_from_defaults(cfg_dir):
    cfg_dir.mkdir()
    (cfg_dir / "catalog.json").write_text(
        json.dumps({"printers": [{"id": "x", "name": "X", "watts": 100}]}))
    r = load_state(legacy_paths=[])
    assert [p.id for p in r.catalog.printers] == ["x"]
    assert len(r.catalog.filaments) == 6
    assert r.warnings == [] and not list(cfg_dir.glob("*.bak-*"))


def test_empty_printers_filled_from_defaults(cfg_dir):
    cfg_dir.mkdir()
    fil = {"id": "mine", "name": "Mine", "type": "PLA", "price_per_kg": 1.0}
    (cfg_dir / "catalog.json").write_text(json.dumps({"printers": [], "filaments": [fil]}))
    r = load_state(legacy_paths=[])
    assert len(r.catalog.printers) == 15
    assert [f.id for f in r.catalog.filaments] == ["mine"]
    assert r.warnings == [] and not list(cfg_dir.glob("*.bak-*"))


def test_no_migration_when_catalog_exists(cfg_dir, tmp_path):
    cfg_dir.mkdir()
    save_catalog(default_catalog(123.0), cfg_dir)
    legacy = tmp_path / "pricing_config.json"
    legacy.write_text(json.dumps({"margin": 40, "power": 200}))
    r = load_state(legacy_paths=[legacy])
    assert r.warnings == [] and r.settings.margin_pct == 50
    assert r.catalog.default_filament().price_per_kg == 123.0


def test_migrate_rejects_non_finite_and_non_positive(cfg_dir, tmp_path):
    legacy = tmp_path / "pricing_config.json"
    legacy.write_text('{"filament_cost": 0, "power": -5, "margin": Infinity, "rate": NaN, "packaging": 7}')
    r = load_state(legacy_paths=[legacy])
    assert r.catalog.default_filament().price_per_kg == 800.0
    assert r.catalog.printers[0].id != "my-printer"
    assert r.settings.margin_pct == 50 and r.settings.electricity_rate == 12
    assert r.settings.default_packaging == 7
