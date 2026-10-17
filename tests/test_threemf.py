import io
import zipfile

import pytest
from pytest import approx

from pcc.core.threemf import ThreeMFError, parse_3mf
from tests.fixtures.make3mf import MULTI_PLATE_PROJECT, build_3mf

PLATE = {"index": 1, "prediction": 60, "weight": 5,
         "filaments": [{"id": 1, "type": "PLA", "color": "#000", "used_g": 5}]}


def test_multi_plate_project():
    p = parse_3mf(MULTI_PLATE_PROJECT, "cube.gcode.3mf")
    assert [pl.index for pl in p.plates] == [1, 2]
    assert p.plates[0].hours == approx(12300 / 3600)
    assert [(f.slot, f.type, f.grams) for f in p.plates[0].filaments] == [(1, "PLA", 42.1), (2, "PETG", 3.0)]
    assert p.plates[0].filaments[0].preset_name == "Bambu PLA Basic @BBL P1S"
    assert p.plates[0].name == "cube · Plate 1"
    assert p.printer_model == "Bambu Lab P1S"
    assert p.printer_settings_id == "Bambu Lab P1S 0.4 nozzle"
    assert p.plates[0].thumbnail_png.startswith(b"\x89PNG")
    assert p.source_name == "cube.gcode.3mf"


def test_plate_name_from_model_settings():
    data = build_3mf([PLATE], model_settings_names={1: "Brackets"})
    assert parse_3mf(data, "x.3mf").plates[0].name == "Brackets"


def test_plate_name_from_slice_info_metadata():
    import zipfile as zf
    src = build_3mf([PLATE], model_settings_names={1: "Brackets"})
    out = io.BytesIO()
    with zf.ZipFile(io.BytesIO(src)) as zin, zf.ZipFile(out, "w") as zout:
        for n in zin.namelist():
            d = zin.read(n)
            if n.endswith("slice_info.config"):
                d = d.replace(b'<metadata key="index"', b'<metadata key="plate_name" value="Named"/><metadata key="index"')
            zout.writestr(n, d)
    assert parse_3mf(out.getvalue(), "x.3mf").plates[0].name == "Named"


def test_missing_project_settings_ok():
    p = parse_3mf(build_3mf([PLATE]), "x.3mf")
    assert p.printer_model is None and p.printer_settings_id is None
    assert p.plates[0].filaments[0].preset_name is None
    assert p.plates[0].name == "x · Plate 1"


def test_invalid_project_settings_json_tolerated():
    src = build_3mf([PLATE], project_settings={"a": 1})
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src)) as zin, zipfile.ZipFile(out, "w") as zout:
        for n in zin.namelist():
            zout.writestr(n, b"{not json" if n.endswith("project_settings.config") else zin.read(n))
    p = parse_3mf(out.getvalue(), "x.3mf")
    assert p.printer_model is None and len(p.plates) == 1


def test_no_thumbnail():
    p = parse_3mf(build_3mf([PLATE], thumbnails=False), "x.3mf")
    assert p.plates[0].thumbnail_png is None


def test_zero_gram_slots_dropped():
    data = build_3mf([{"index": 1, "prediction": 60, "weight": 5, "filaments": [
        {"id": 1, "type": "PLA", "color": "#000", "used_g": 5}, {"id": 2, "type": "PETG", "color": "#fff", "used_g": 0}]},
        {"index": 2, "prediction": 60, "weight": 0, "filaments": [{"id": 1, "type": "PLA", "color": "#000", "used_g": 0}]}])
    p = parse_3mf(data, "x.3mf")
    assert len(p.plates) == 1 and len(p.plates[0].filaments) == 1


def test_tolerant_bad_numbers():
    src = build_3mf([PLATE])
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src)) as zin, zipfile.ZipFile(out, "w") as zout:
        for n in zin.namelist():
            d = zin.read(n)
            if n.endswith("slice_info.config"):
                d = d.replace(b'value="60"', b'value="abc"')
            zout.writestr(n, d)
    assert parse_3mf(out.getvalue(), "x.3mf").plates[0].seconds == 0


def test_path_and_filelike(tmp_path):
    f = tmp_path / "Part.3MF"
    f.write_bytes(MULTI_PLATE_PROJECT)
    assert parse_3mf(f).plates[0].name == "Part · Plate 1"
    assert parse_3mf(io.BytesIO(MULTI_PLATE_PROJECT), "q.3mf").source_name == "q.3mf"


def test_not_a_zip():
    with pytest.raises(ThreeMFError, match=r"^Not a valid \.3mf file\.$"):
        parse_3mf(b"hello", "a.3mf")


def test_zip_bomb_guard():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Metadata/slice_info.config", b"0" * (51 * 1024 * 1024))
    with pytest.raises(ThreeMFError, match=r"^Not a valid \.3mf file\.$"):
        parse_3mf(buf.getvalue(), "a.3mf")


def test_unsliced():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("3D/3dmodel.model", "<model/>")
    msg = "No slice data. In Bambu Studio/OrcaSlicer use 'Export plate sliced file' or 'Export all sliced files'."
    with pytest.raises(ThreeMFError) as e:
        parse_3mf(buf.getvalue(), "a.3mf")
    assert str(e.value) == msg


def test_all_plates_empty_is_no_slice_data():
    with pytest.raises(ThreeMFError, match="^No slice data"):
        parse_3mf(build_3mf([{**PLATE, "filaments": []}]), "a.3mf")
