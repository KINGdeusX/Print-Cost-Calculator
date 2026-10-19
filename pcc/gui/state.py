"""GUI model/controller: owns settings, catalog, the current job and its quote."""

from __future__ import annotations

import time
import weakref
from dataclasses import fields as dc_fields
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from pcc.core.matching import match_printer, project_to_plates
from pcc.core.models import (
    Catalog, FilamentUse, Job, Plate, Settings, new_id, new_job,
)
from pcc.core.projects import (
    InvoiceRecord, Project, ProjectError, create_project, load_project, save_project,
)
from pcc.core.pricing import PricingError, Quote, compute_quote
from pcc.core.storage import load_state, save_catalog, save_settings
from pcc.core.threemf import ThreeMFError, parse_3mf

SAVE_DELAY_MS = 500
SAVE_ATTEMPTS = 3
SAVE_RETRY_DELAY_S = 0.1
_INSTANCES: "weakref.WeakSet[AppState]" = weakref.WeakSet()
_REPAIRED = "Some items used a deleted profile and were switched to the default."
_PLATE_FIELDS = {f.name for f in dc_fields(Plate)} - {"id"}
_JOB_FIELDS = {"customer", "printer_id", "packaging"}
_SETTINGS_FIELDS = {f.name for f in dc_fields(Settings)}


class AppState(QObject):
    quote_changed = Signal(object)
    job_changed = Signal()
    catalog_changed = Signal()
    settings_changed = Signal()
    warning = Signal(str)
    project_opened = Signal()
    project_closed = Signal()
    dirty_changed = Signal(bool)
    projects_changed = Signal()
    project_renamed = Signal(str)

    def __init__(self, directory: Path | None = None,
                 legacy_paths: list[Path] | None = None):
        super().__init__()
        self._directory = directory
        result = load_state(directory, legacy_paths)
        self.settings: Settings = result.settings
        self.catalog: Catalog = result.catalog
        self.pending_warnings: list[str] = list(result.warnings)
        self.quote: Quote | None = None
        self.last_error: str | None = None
        self.project: Project | None = None
        self.project_path: Path | None = None
        self.dirty = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SAVE_DELAY_MS)
        self._timer.timeout.connect(self._save)
        _INSTANCES.add(self)
        self.job: Job = self._fresh_job()
        self._compute()

    # -- persistence -------------------------------------------------
    def _schedule_save(self) -> None:
        self._timer.start()

    def _save(self) -> None:
        # Windows AV/OneDrive can briefly lock the files: retry, then warn.
        for attempt in range(SAVE_ATTEMPTS):
            try:
                save_settings(self.settings, self._directory)
                save_catalog(self.catalog, self._directory)
                return
            except OSError as e:
                error = e
                if attempt + 1 < SAVE_ATTEMPTS:
                    time.sleep(SAVE_RETRY_DELAY_S)
        self.warning.emit(f"Could not save settings: {error.strerror or error}")

    def shutdown(self) -> None:
        """Stop the pending debounced save without writing."""
        self._timer.stop()

    def flush(self) -> None:
        self._timer.stop()
        self._save()

    # -- quote -------------------------------------------------------
    def _compute(self) -> None:
        if not self.job.plates:
            self.quote, self.last_error = None, None
            return
        try:
            self.quote = compute_quote(self.job, self.settings, self.catalog)
            self.last_error = None
        except PricingError as e:
            self.quote, self.last_error = None, str(e)

    def recalc(self) -> None:
        self._compute()
        self.quote_changed.emit(self.quote)

    # -- job ---------------------------------------------------------
    def _fresh_job(self) -> Job:
        pid = self.settings.last_printer_id
        if not (pid and self.catalog.printer(pid)):
            pid = self.catalog.default_printer().id
        return new_job(pid, self.settings.default_packaging)

    def _set_dirty(self, value: bool) -> None:
        if self.dirty != value:
            self.dirty = value
            self.dirty_changed.emit(value)

    def _mark_dirty(self) -> None:
        # Without an open project there is nothing to save.
        if self.project is not None:
            self._set_dirty(True)

    def _blank_plate(self) -> Plate:
        return Plate(
            id=new_id("plate"), name=f"Plate {len(self.job.plates) + 1}", hours=0.0,
            filaments=[FilamentUse(self.catalog.default_filament().id, 0.0)],
            labor=self.settings.default_labor,
        )

    def add_plate(self, plate: Plate | None = None) -> Plate:
        plate = plate or self._blank_plate()
        self.job.plates.append(plate)
        self._mark_dirty()
        self.job_changed.emit()
        self.recalc()
        return plate

    def remove_plate(self, plate_id: str) -> None:
        self.job.plates = [p for p in self.job.plates if p.id != plate_id]
        self._mark_dirty()
        self.job_changed.emit()
        self.recalc()

    def update_plate(self, plate_id: str, **fields) -> None:
        plate = next((p for p in self.job.plates if p.id == plate_id), None)
        if plate is None:
            raise ValueError(f"unknown plate id: {plate_id}")
        bad = set(fields) - _PLATE_FIELDS
        if bad:
            raise ValueError(f"unknown plate field: {sorted(bad)[0]}")
        for k, v in fields.items():
            setattr(plate, k, list(v) if k == "filaments" else v)
        self._mark_dirty()
        self.job_changed.emit()
        self.recalc()

    def update_job(self, **fields) -> None:
        bad = set(fields) - _JOB_FIELDS
        if bad:
            raise ValueError(f"unknown job field: {sorted(bad)[0]}")
        for k, v in fields.items():
            setattr(self.job, k, v)
        self._mark_dirty()
        if fields.get("printer_id"):
            self.settings.last_printer_id = fields["printer_id"]
            self._schedule_save()
        self.job_changed.emit()
        self.recalc()

    def update_settings(self, **fields) -> None:
        bad = set(fields) - _SETTINGS_FIELDS
        if bad:
            raise ValueError(f"unknown settings field: {sorted(bad)[0]}")
        for k, v in fields.items():
            setattr(self.settings, k, v)
        self._schedule_save()
        self.settings_changed.emit()
        self.recalc()

    def _repair_job(self) -> bool:
        """Point unknown printer/filament ids at the defaults; True if changed."""
        repaired = False
        default_fid = self.catalog.default_filament().id
        for plate in self.job.plates:
            for use in plate.filaments:
                if self.catalog.filament(use.filament_id) is None:
                    use.filament_id = default_fid
                    repaired = True
        if self.catalog.printer(self.job.printer_id) is None:
            self.job.printer_id = self.catalog.default_printer().id
            repaired = True
        if repaired:
            self._mark_dirty()
        return repaired

    def set_catalog(self, catalog: Catalog) -> None:
        self.catalog = catalog
        repaired = self._repair_job()
        if self.settings.last_printer_id and not catalog.printer(
                self.settings.last_printer_id):
            self.settings.last_printer_id = ""
        self._schedule_save()
        self.catalog_changed.emit()
        self.job_changed.emit()
        if repaired:
            self.warning.emit(_REPAIRED)
        self.recalc()

    # -- import ------------------------------------------------------
    def import_files(self, paths: list[Path]) -> list[tuple[str, str]]:
        failures: list[tuple[str, str]] = []
        matched: str | None = None
        added = False
        for path in paths:
            path = Path(path)
            try:
                project = parse_3mf(path.read_bytes(), path.name)
            except OSError:
                failures.append((path.name, "Could not read file."))
                continue
            except ThreeMFError as e:
                failures.append((path.name, str(e)))
                continue
            self.job.plates.extend(
                project_to_plates(project, self.catalog, self.settings))
            added = True
            pid = match_printer(project, self.catalog, matched or self.job.printer_id)
            if pid:
                matched = pid
        if matched:
            self.job.printer_id = matched
            self.settings.last_printer_id = matched
            self._schedule_save()
        if added:
            self._mark_dirty()
        if added or matched:
            self.job_changed.emit()
            self.recalc()
        return failures

    # -- projects ----------------------------------------------------
    def _load_into_state(self, path: Path | None, project: Project | None) -> None:
        self.project, self.project_path = project, path
        self.job = project.job if project else self._fresh_job()
        self._set_dirty(False)

    def new_project(self, name: str = "Untitled project") -> Path:
        handle = create_project(name, self._fresh_job())
        self._load_into_state(handle.path, handle.project)
        self.job_changed.emit()
        self.recalc()
        self.project_opened.emit()
        self.projects_changed.emit()
        return handle.path

    def open_project(self, path: Path) -> None:
        project = load_project(Path(path))
        self._load_into_state(Path(path), project)
        repaired = self._repair_job()
        self.job_changed.emit()
        self.recalc()
        if repaired:
            self.warning.emit(_REPAIRED)
        self.project_opened.emit()

    def save_project(self, force: bool = False) -> None:
        if self.project is None or self.project_path is None:
            return
        current = replace(self.project, job=self.job)
        expected = None if force else self.project.updated_at
        # Windows AV/OneDrive can briefly lock the files: retry, then raise.
        for attempt in range(SAVE_ATTEMPTS):
            try:
                self.project = save_project(self.project_path, current, expected)
                break
            except PermissionError:
                if attempt + 1 == SAVE_ATTEMPTS:
                    raise
                time.sleep(SAVE_RETRY_DELAY_S)
        self._set_dirty(False)
        self.projects_changed.emit()

    def close_project(self) -> None:
        self._load_into_state(None, None)
        self.job_changed.emit()
        self.recalc()
        self.project_closed.emit()

    def rename_current(self, name: str) -> None:
        name = name.strip()
        if self.project is None or not name:
            return
        self.project = replace(self.project, name=name)
        self._set_dirty(True)
        self.project_renamed.emit(name)

    def record_invoice(self, record: InvoiceRecord) -> None:
        if self.project is None:
            return
        kept = [r for r in self.project.invoices
                if not (r.number == record.number and r.file == record.file)]
        self.project = replace(self.project, invoices=[*kept, record])
        self._set_dirty(True)  # stays dirty if the save below raises
        self.save_project()

    def create_projects_from_files(
            self, paths: list[Path]) -> tuple[list[Path], list[tuple[str, str]]]:
        created: list[Path] = []
        failures: list[tuple[str, str]] = []
        for path in paths:
            path = Path(path)
            try:
                parsed = parse_3mf(path.read_bytes(), path.name)
            except OSError:
                failures.append((path.name, "Could not read file."))
                continue
            except ThreeMFError as e:
                failures.append((path.name, str(e)))
                continue
            job = self._fresh_job()
            job.plates.extend(project_to_plates(parsed, self.catalog, self.settings))
            pid = match_printer(parsed, self.catalog, job.printer_id)
            if pid:
                job.printer_id = pid
            name = path.name
            for suffix in (".gcode.3mf", ".3mf"):
                if name.lower().endswith(suffix):
                    name = name[:-len(suffix)]
                    break
            try:
                created.append(create_project(name or "Untitled project", job).path)
            except (OSError, ProjectError) as e:
                failures.append((path.name, f"Could not save project: {e}"))
        if created:
            self.projects_changed.emit()
        return created, failures
