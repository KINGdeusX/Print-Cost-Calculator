"""JSON-friendly dict views of the data model (spec: serialization)."""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from datetime import datetime
from typing import Any, Literal

from pcc.core.models import (
    Catalog, Filament, FilamentUse, Job, Plate, PrinterProfile, Settings,
)
from pcc.core.pricing import Quote


def _build(cls, d: dict[str, Any], **overrides):
    """Construct dataclass `cls` from `d`, ignoring unknown keys."""
    names = {f.name for f in fields(cls)}
    kwargs = {k: v for k, v in d.items() if k in names}
    kwargs.update(overrides)
    return cls(**kwargs)


def settings_to_dict(s: Settings) -> dict:
    return asdict(s)


def settings_from_dict(d: dict) -> Settings:
    return _build(Settings, d)


def catalog_to_dict(c: Catalog) -> dict:
    return asdict(c)


def catalog_from_dict(d: dict) -> Catalog:
    return Catalog(
        printers=[_build(PrinterProfile, p) for p in d.get("printers", [])],
        filaments=[_build(Filament, f) for f in d.get("filaments", [])],
    )


def job_to_dict(job: Job) -> dict:
    d = asdict(job)
    d["created_at"] = job.created_at.isoformat()
    for p in d["plates"]:
        p.pop("thumbnail_png", None)
    return d


def job_from_dict(d: dict) -> Job:
    plates = []
    for p in d.get("plates", []):
        uses = [_build(FilamentUse, u) for u in p.get("filaments", [])]
        p = {k: v for k, v in p.items() if k != "thumbnail_png"}
        plates.append(_build(Plate, p, filaments=uses))
    return _build(
        Job, d, created_at=datetime.fromisoformat(d["created_at"]), plates=plates
    )


def quote_to_dict(quote: Quote, view: Literal["public", "internal"] = "public") -> dict:
    internal = view == "internal"
    plates = []
    for p in quote.plates:
        item = {
            "plate_id": p.plate_id, "name": p.name, "copies": p.copies,
            "hours": p.hours, "grams": p.grams, "price": p.price,
            "price_total": p.price_total,
        }
        if internal:
            item["costs"] = asdict(p.per_copy)
            item["cost"] = p.cost
            item["cost_total"] = p.cost_total
            item["internal_fee_total"] = p.internal_fee_total
        plates.append(item)
    out: dict[str, Any] = {
        "job_id": quote.job_id,
        "currency": {"code": quote.currency_code, "symbol": quote.currency_symbol},
        "plates": plates,
        "total_hours": quote.total_hours,
        "total_grams": quote.total_grams,
        "total_copies": quote.total_copies,
        "price": quote.price,
    }
    if internal:
        out["lines"] = asdict(quote.lines)
        out["packaging"] = quote.packaging
        out["job_cost"] = quote.job_cost
        out["price_raw"] = quote.price_raw
        out["markup"] = quote.markup
        out["internal_fee"] = quote.internal_fee
    return out


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
