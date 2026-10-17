"""Map parsed .3mf data onto the printer/filament catalog."""

from __future__ import annotations

from pcc.core.models import Catalog, FilamentUse, Plate, Settings, new_id
from pcc.core.threemf import ParsedFilament, ParsedProject


def match_printer(project: ParsedProject, catalog: Catalog) -> str | None:
    for text in (project.printer_model, project.printer_settings_id):
        if not text:
            continue
        hay = text.casefold()
        for printer in catalog.printers:
            if any(m and m.casefold() in hay for m in printer.model_match):
                return printer.id
    return None


def match_filament(pf: ParsedFilament, catalog: Catalog) -> tuple[str, str]:
    if pf.preset_name:
        key = pf.preset_name.split(" @")[0].strip().casefold()
        for f in catalog.filaments:
            if f.name.casefold() == key:
                return f.id, "exact"
    same = [f for f in catalog.filaments if f.type.casefold() == pf.type.casefold()]
    if same:
        pick = next((f for f in same if f.is_default), same[0])
        return pick.id, "type"
    return catalog.default_filament().id, "default"


def project_to_plates(
    project: ParsedProject, catalog: Catalog, settings: Settings
) -> list[Plate]:
    plates = []
    for pp in project.plates:
        uses = []
        for pf in pp.filaments:
            fid, kind = match_filament(pf, catalog)
            uses.append(FilamentUse(
                filament_id=fid, grams=pf.grams, slot=pf.slot,
                source_type=pf.type, source_name=pf.preset_name,
                source_color=pf.color, match=kind,
            ))
        plates.append(Plate(
            id=new_id("plate"), name=pp.name, hours=pp.hours, filaments=uses,
            labor=settings.default_labor, copies=1, source_file=project.source_name,
            plate_index=pp.index, thumbnail_png=pp.thumbnail_png,
        ))
    return plates
