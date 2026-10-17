import json

from pytest import approx

from pcc.core.models import new_job
from pcc.core.serialize import (
    catalog_from_dict, catalog_to_dict, dumps, job_from_dict, job_to_dict,
    quote_to_dict, settings_from_dict, settings_to_dict,
)

PRIVATE = {"internal_fee", "internal_fee_total", "markup", "job_cost", "costs", "lines",
           "margin_pct", "hidden_plate_fee", "price_per_kg"}


def _all_keys(o):
    keys = set()
    if isinstance(o, dict):
        for k, v in o.items():
            keys.add(k)
            keys |= _all_keys(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            keys |= _all_keys(v)
    return keys


def test_public_quote_hides_internal(quote):
    d = quote_to_dict(quote)
    assert not (_all_keys(d) & PRIVATE)
    assert set(d) == {"job_id", "currency", "plates", "total_hours", "total_grams",
                      "total_copies", "price"}
    assert d["currency"] == {"code": "PHP", "symbol": "₱"}
    assert set(d["plates"][0]) == {"plate_id", "name", "copies", "hours", "grams",
                                   "price", "price_total"}


def test_internal_quote_has_costs(quote):
    d = quote_to_dict(quote, "internal")
    assert d["internal_fee"] == approx(60) and "costs" in d["plates"][0]
    assert set(d["plates"][0]["costs"]) == {"filament", "electricity", "failure", "labor"}
    assert {"lines", "packaging", "job_cost", "price_raw", "markup"} <= set(d)
    assert {"cost", "cost_total", "internal_fee_total"} <= set(d["plates"][0])


def test_settings_unknown_and_missing_keys():
    s = settings_from_dict({"margin_pct": 70, "future_key": 1})
    assert s.margin_pct == 70 and s.rounding_step == 5


def test_settings_round_trip(settings):
    assert settings_from_dict(settings_to_dict(settings)) == settings


def test_catalog_round_trip_and_tolerance(catalog):
    assert catalog_from_dict(catalog_to_dict(catalog)) == catalog
    c = catalog_from_dict({"printers": [{"id": "x", "name": "X", "watts": 100, "zzz": 1}],
                           "filaments": [{"id": "f", "name": "F", "type": "PLA",
                                          "price_per_kg": 900, "extra": 2}], "new": 1})
    assert c.printers[0].model_match == [] and c.filaments[0].color == "#808080"
    assert catalog_from_dict({}).printers == []


def test_job_round_trip(job):
    job.plates[0].thumbnail_png = b"png"
    d = job_to_dict(job)
    assert "thumbnail_png" not in d["plates"][0]
    assert d["created_at"] == "2026-10-17T12:00:00"
    j2 = job_from_dict(json.loads(dumps(d)))
    job.plates[0].thumbnail_png = None
    assert j2 == job


def test_job_from_dict_tolerant(job):
    d = job_to_dict(job)
    d["bogus"] = 1
    d["plates"][0]["bogus"] = 1
    d["plates"][0]["filaments"][0]["bogus"] = 1
    del d["customer"]
    assert job_from_dict(d).customer == ""


def test_job_round_trip_unicode():
    job = new_job("p1", 20, customer="Niño 🎉 Café")
    assert job_from_dict(json.loads(dumps(job_to_dict(job)))).customer == "Niño 🎉 Café"
    assert "Niño 🎉" in dumps(job_to_dict(job))
