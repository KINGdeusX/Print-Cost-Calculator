from pcc.core.matching import match_filament, match_printer, project_to_plates
from pcc.core.models import Catalog, Filament, Settings
from pcc.core.storage import default_catalog
from pcc.core.threemf import ParsedFilament, ParsedProject, parse_3mf
from tests.fixtures.make3mf import MULTI_PLATE_PROJECT


def _pf(type_="PLA", preset=None):
    return ParsedFilament(slot=1, type=type_, color="#FFF", grams=5.0, preset_name=preset)


def test_exact_match_strips_at_suffix():
    cat = Catalog(filaments=[
        Filament("a", "Generic PLA", "PLA", 800, is_default=True),
        Filament("b", "Bambu PLA Basic", "PLA", 900),
    ])
    assert match_filament(_pf(preset="bambu pla basic @BBL P1S"), cat) == ("b", "exact")


def test_type_match_prefers_default():
    cat = Catalog(filaments=[
        Filament("pla", "Generic PLA", "PLA", 800, is_default=True),
        Filament("p1", "PETG One", "PETG", 800),
        Filament("p2", "PETG Two", "PETG", 800, is_default=True),
    ])
    assert match_filament(_pf("petg", "Unknown"), cat) == ("p2", "type")
    cat.set_default_filament("pla")
    assert match_filament(_pf("PETG"), cat) == ("p1", "type")


def test_fallback_default():
    cat = default_catalog()
    assert match_filament(_pf("PVA", "x"), cat) == ("pla", "default")


def test_printer_model_match():
    cat = default_catalog()
    proj = ParsedProject("a.3mf", "Bambu Lab P1S", None, [])
    assert match_printer(proj, cat) == "bambu-p1s"
    assert match_printer(ParsedProject("a", "Prusa MK4", None, []), cat) is None
    assert match_printer(ParsedProject("a", None, None, []), cat) is None
    proj = ParsedProject("a", None, "Bambu Lab p1s 0.4 nozzle", [])
    assert match_printer(proj, cat) == "bambu-p1s"


def test_project_to_plates():
    cat = default_catalog()
    settings = Settings(default_labor=7.0)
    proj = parse_3mf(MULTI_PLATE_PROJECT, "cube.gcode.3mf")
    plates = project_to_plates(proj, cat, settings)
    assert len(plates) == 2
    p = plates[0]
    assert p.id.startswith("plate-") and p.id != plates[1].id
    assert p.labor == 7.0 and p.copies == 1
    assert p.name == "cube · Plate 1" and p.source_file == "cube.gcode.3mf"
    assert p.plate_index == 1 and p.thumbnail_png
    assert p.hours == proj.plates[0].hours
    f = p.filaments
    assert [(u.filament_id, u.match, u.grams, u.slot) for u in f] == [
        ("pla", "type", 42.1, 1), ("petg", "type", 3.0, 2)]
    assert f[0].source_type == "PLA"
    assert f[0].source_name == "Bambu PLA Basic @BBL P1S"
    assert f[0].source_color == "#FFFFFF"
