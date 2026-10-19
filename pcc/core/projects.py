"""Project store: one folder per project under the Projects data directory."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

from pcc.core.models import Job, new_id
from pcc.core.paths import projects_dir
from pcc.core.serialize import job_from_dict, job_to_dict
from pcc.core.storage import atomic_write_text

_ONE_US = timedelta(microseconds=1)
PROJECT_FILE = "project.json"
THUMBS_DIR = "thumbs"
_LOAD_ERRORS = (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError,
                AttributeError, RecursionError)
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ProjectError(Exception):
    pass


class ProjectConflictError(ProjectError):
    pass


@dataclass
class InvoiceRecord:
    number: str
    date: str
    bill_to: str
    total: float
    currency_symbol: str
    file: str


@dataclass
class Project:
    id: str
    name: str
    created_at: str
    updated_at: str
    job: Job
    invoices: list[InvoiceRecord] = field(default_factory=list)
    schema_version: int = 1


@dataclass
class ProjectHandle:
    path: Path
    project: Project


def _now() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def safe_name(name: str) -> str:
    s = _ILLEGAL.sub("", name)
    s = " ".join(s.split())
    s = s[:60]
    s = s.encode("utf-8")[:100].decode("utf-8", "ignore").rstrip(". ")
    stem, dot, ext = s.partition(".")
    if stem.rstrip(" ").upper() in _RESERVED:
        s = stem + "_" + dot + ext
    return s or "Project"


# -- (de)serialization (private: jobs.project_to_dict is a different thing) ----

def _to_dict(p: Project) -> dict:
    return {
        "schema_version": p.schema_version, "id": p.id, "name": p.name,
        "created_at": p.created_at, "updated_at": p.updated_at,
        "job": job_to_dict(p.job),
        "invoices": [vars(r).copy() for r in p.invoices],
    }


def _from_dict(d: dict) -> Project:
    return Project(
        id=d["id"], name=d["name"], created_at=d["created_at"],
        updated_at=d["updated_at"], job=job_from_dict(d["job"]),
        invoices=[InvoiceRecord(**r) for r in d.get("invoices", [])],
        schema_version=d.get("schema_version", 1),
    )


def _read(path: Path) -> Project:
    text = (path / PROJECT_FILE).read_text(encoding="utf-8")
    d = json.loads(text)
    if not isinstance(d, dict):
        raise ValueError("project.json must be an object")
    return _from_dict(d)


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _thumb_path(path: Path, plate_id: str) -> Path | None:
    if not plate_id or plate_id in (".", "..") or re.search(r'[/\\\x00]', plate_id):
        return None
    return path / THUMBS_DIR / f"{plate_id}.png"


def _write(path: Path, project: Project) -> None:
    """Write project.json and sync thumbs (write changed, remove stale)."""
    keep: set[Path] = set()
    for plate in project.job.plates:
        tp = _thumb_path(path, plate.id)
        if tp is None:
            continue
        keep.add(tp)
        if plate.thumbnail_png is not None:
            try:
                if tp.read_bytes() == plate.thumbnail_png:
                    continue
            except OSError:
                pass
            _write_bytes_atomic(tp, plate.thumbnail_png)
        # thumbnail None: keep any existing file (not loaded, e.g. from list)
    atomic_write_text(
        path / PROJECT_FILE,
        json.dumps(_to_dict(project), ensure_ascii=False, indent=2),
    )
    tdir = path / THUMBS_DIR
    plate_ids = {pl.id for pl in project.job.plates}
    if tdir.is_dir():
        for f in tdir.glob("*.png"):
            if f.stem not in plate_ids:
                try:
                    f.unlink()
                except OSError:
                    pass


# -- public API ---------------------------------------------------------------

def list_projects(root: Path | None = None) -> tuple[list[ProjectHandle], list[str]]:
    try:
        root = root or projects_dir()
    except OSError as e:  # read-only / missing drive: start anyway, say why
        return [], [f"Projects folder unavailable: {e.strerror or e}"]
    handles: list[ProjectHandle] = []
    warnings: list[str] = []
    try:
        folders = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return [], []
    for folder in folders:
        if not (folder / PROJECT_FILE).exists():
            continue
        try:
            handles.append(ProjectHandle(folder, _read(folder)))
        except _LOAD_ERRORS:
            warnings.append(f"{folder.name}: could not be read")
    handles.sort(key=lambda h: h.project.updated_at, reverse=True)
    return handles, warnings


def create_project(name: str, job: Job, root: Path | None = None) -> ProjectHandle:
    root = root or projects_dir()
    now = _now()
    for _ in range(5):
        project = Project(id=new_id("proj"), name=name, created_at=now,
                          updated_at=now, job=job)
        folder = root / f"{now[:10]} {safe_name(name)} ({project.id[-6:]})"
        try:
            folder.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        _write(folder, project)
        return ProjectHandle(folder, project)
    raise ProjectError(f"could not create a folder for '{name}'")


def load_project(path: Path) -> Project:
    try:
        project = _read(path)
    except _LOAD_ERRORS as e:
        raise ProjectError(f"{path.name}: could not be read") from e
    for plate in project.job.plates:
        tp = _thumb_path(path, plate.id)
        if tp is not None and tp.is_file():
            try:
                plate.thumbnail_png = tp.read_bytes()
            except OSError:
                pass
    return project


def save_project(path: Path, project: Project,
                 expected_updated_at: str | None) -> Project:
    """Save and return a NEW Project carrying the new `updated_at`.

    The caller's object is not mutated. Raises ProjectConflictError when the
    on-disk `updated_at` differs from `expected_updated_at` (None = force).
    """
    old = ""
    if not (path / PROJECT_FILE).exists():
        if expected_updated_at is not None:
            raise ProjectConflictError(f"{path.name}: deleted elsewhere")
    else:
        try:
            old = _read(path).updated_at
        except _LOAD_ERRORS:
            old = ""
        if expected_updated_at is not None and old != expected_updated_at:
            raise ProjectConflictError(f"{path.name}: changed elsewhere")
    now = _now()
    if old and now <= old:  # clock granularity / skew: stay strictly increasing
        now = (datetime.fromisoformat(old) + _ONE_US).isoformat(timespec="microseconds")
    saved = replace(project, updated_at=now)
    _write(path, saved)
    return saved


def duplicate_project(path: Path, new_name: str) -> ProjectHandle:
    src = load_project(path)
    job = replace(src.job, plates=[replace(p) for p in src.job.plates])
    handle = create_project(new_name, job, root=path.parent)
    return handle


def rename_project(path: Path, new_name: str) -> Project:
    project = load_project(path)
    return save_project(path, replace(project, name=new_name), None)
