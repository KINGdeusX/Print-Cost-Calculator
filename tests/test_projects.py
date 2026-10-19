import base64
from dataclasses import replace

import pytest

from pcc.core.paths import projects_dir
from pcc.core.projects import (
    ProjectConflictError, ProjectError, create_project, duplicate_project,
    list_projects, load_project, rename_project, safe_name, save_project,
)

PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/"
    "iZk9HQAAAABJRU5ErkJggg==")


def test_create_list_load_roundtrip(data_dir, job):
    job.plates[0].thumbnail_png = PNG_1x1
    h = create_project("Benchy order", job)
    handles, warnings = list_projects()
    assert [x.project.name for x in handles] == ["Benchy order"] and warnings == []
    assert handles[0].project.job.plates[0].thumbnail_png is None
    p = load_project(h.path)
    assert p.job.plates[0].thumbnail_png == PNG_1x1 and p.job.customer == job.customer


def test_sorted_by_updated_desc(data_dir, job):
    a, b = create_project("A", job), create_project("B", job)
    assert [x.project.name for x in list_projects()[0]] == ["B", "A"]
    p = load_project(a.path)
    save_project(a.path, p, p.updated_at)
    assert [x.project.name for x in list_projects()[0]] == ["A", "B"]


@pytest.mark.parametrize("name", ['a/b:c*?', "CON", "nul.txt", "x. ", "é" * 200, "🎉 order", "🎉" * 60])
def test_unsafe_names(data_dir, job, name):
    h = create_project(name, job)
    assert h.path.is_dir() and load_project(h.path).name == name
    stem = h.path.name.split(" ", 1)[1].rsplit(" (", 1)[0]
    assert stem.upper().split(".")[0] not in {"CON", "NUL"} and not stem.endswith((".", " "))


def test_safe_name_edge_cases():
    assert safe_name("") == "Project" and safe_name("///") == "Project"
    assert safe_name("com1") == "com1_" and safe_name("nul.txt") == "nul_.txt" and safe_name("a  b") == "a b"
    assert len(safe_name("x" * 100)) == 60


def test_same_name_twice_distinct(data_dir, job):
    a, b = create_project("Same", job), create_project("Same", job)
    assert a.path != b.path and len(list_projects()[0]) == 2


def test_conflict_detected(data_dir, job):
    h = create_project("P", job)
    p = load_project(h.path)
    new = save_project(h.path, p, p.updated_at)
    assert new.updated_at > p.updated_at and p.updated_at != new.updated_at
    with pytest.raises(ProjectConflictError):
        save_project(h.path, p, p.updated_at)
    save_project(h.path, p, None)


def test_damaged_project_skipped(data_dir, job):
    create_project("Good", job)
    bad = projects_dir() / "broken"
    bad.mkdir()
    (bad / "project.json").write_text("{", encoding="utf-8")
    (projects_dir() / "not-a-project").mkdir()
    handles, warnings = list_projects()
    assert len(handles) == 1 and warnings == ["broken: could not be read"]
    with pytest.raises(ProjectError):
        load_project(bad)


def test_duplicate_new_id_copies_thumbs_no_invoices(data_dir, job):
    from pcc.core.projects import InvoiceRecord
    job.plates[0].thumbnail_png = PNG_1x1
    h = create_project("Orig", job)
    p = load_project(h.path)
    p.invoices.append(InvoiceRecord("INV-0001", "2026-01-01", "X", 1.0, "$", "/x.pdf"))
    save_project(h.path, p, None)
    d = duplicate_project(h.path, "Copy")
    q = load_project(d.path)
    assert d.path != h.path and q.id != p.id and q.name == "Copy"
    assert q.invoices == [] and q.job.plates[0].thumbnail_png == PNG_1x1
    assert len(load_project(h.path).invoices) == 1


def test_rename_keeps_folder(data_dir, job):
    h = create_project("Old", job)
    p = rename_project(h.path, "New")
    assert p.name == "New" and load_project(h.path).name == "New"
    assert [x.path for x in list_projects()[0]] == [h.path]


def test_deleted_plate_thumb_removed(data_dir, job):
    job.plates[0].thumbnail_png = PNG_1x1
    pid = job.plates[0].id
    h = create_project("T", job)
    assert (h.path / "thumbs" / f"{pid}.png").exists()
    p = load_project(h.path)
    save_project(h.path, replace(p, job=replace(p.job, plates=[])), None)
    assert not (h.path / "thumbs" / f"{pid}.png").exists()


@pytest.mark.parametrize("data", [
    '{"job": "x"}', '{"job": [1]}',
    '{"id":"a","name":"n","created_at":"2026-01-01T00:00:00","updated_at":"u",'
    '"job":{"created_at":"2026-01-01T00:00:00","plates":["x"]}}',
    '{"id":"a","name":"n","created_at":"2026-01-01T00:00:00","updated_at":"u",'
    '"job":{"created_at":"2026-01-01T00:00:00","plates":[null]}}',
])
def test_malformed_shapes_skipped(data_dir, job, data):
    bad = projects_dir() / "odd"
    bad.mkdir()
    (bad / "project.json").write_text(data, encoding="utf-8")
    handles, warnings = list_projects()
    assert handles == [] and warnings == ["odd: could not be read"]
    with pytest.raises(ProjectError):
        load_project(bad)


def test_save_missing_file_conflicts_unless_forced(data_dir, job):
    h = create_project("P", job)
    p = load_project(h.path)
    (h.path / "project.json").unlink()
    with pytest.raises(ProjectConflictError):
        save_project(h.path, p, p.updated_at)
    assert not (h.path / "project.json").exists()
    save_project(h.path, p, None)
    assert (h.path / "project.json").exists()


def test_evil_plate_id_writes_nothing_outside_thumbs(data_dir, job):
    job.plates[0].id = "../evil"
    job.plates[0].thumbnail_png = PNG_1x1
    h = create_project("E", job)
    assert not (h.path / "evil.png").exists()
    assert list(h.path.rglob("*.png")) == []


def test_thumbnail_none_keeps_existing_file(data_dir, job):
    job.plates[0].thumbnail_png = PNG_1x1
    h = create_project("K", job)
    p = list_projects()[0][0].project          # thumbnails not loaded
    save_project(h.path, p, None)
    assert load_project(h.path).job.plates[0].thumbnail_png == PNG_1x1


def test_create_never_overwrites_existing_folder(data_dir, job, monkeypatch):
    import pcc.core.projects as pr
    first = create_project("Same", job)
    ids = iter([first_id := load_project(first.path).id, first_id, "proj-fresh0001"])
    monkeypatch.setattr(pr, "new_id", lambda prefix: next(ids))
    second = create_project("Same", job)
    assert second.path != first.path and second.project.id == "proj-fresh0001"
    assert load_project(first.path).id == first_id
