"""Build a Job from a parsed .3mf project (shared by CLI and API)."""

from __future__ import annotations

from pcc.core.matching import match_printer, project_to_plates
from pcc.core.models import Catalog, Job, Settings, new_job
from pcc.core.pricing import PricingError
from pcc.core.threemf import ParsedProject


def build_job_from_project(
    project: ParsedProject,
    settings: Settings,
    catalog: Catalog,
    printer_id: str | None = None,
    copies: int = 1,
    customer: str = "",
) -> Job:
    if printer_id:
        if catalog.printer(printer_id) is None:
            raise PricingError(f"unknown printer id: {printer_id}")
    else:
        printer_id = match_printer(project, catalog, settings.last_printer_id or None)
        if printer_id is None:
            if settings.last_printer_id and catalog.printer(settings.last_printer_id):
                printer_id = settings.last_printer_id
            else:
                printer_id = catalog.default_printer().id
    job = new_job(printer_id, settings.default_packaging, customer)
    job.plates = project_to_plates(project, catalog, settings)
    if copies and copies != 1:
        for plate in job.plates:
            plate.copies = copies
    return job


def project_to_dict(project: ParsedProject) -> dict:
    """JSON view of a parsed project (no thumbnails, no prices)."""
    return {
        "source_name": project.source_name,
        "printer_model": project.printer_model,
        "printer_settings_id": project.printer_settings_id,
        "plates": [
            {
                "index": p.index, "name": p.name, "hours": p.hours,
                "filaments": [
                    {"slot": f.slot, "type": f.type, "color": f.color,
                     "grams": f.grams, "preset_name": f.preset_name}
                    for f in p.filaments
                ],
            }
            for p in project.plates
        ],
    }
