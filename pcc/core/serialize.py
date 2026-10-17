"""JSON-friendly dict views of the data model (spec: serialization)."""

from __future__ import annotations

import json
import math
from dataclasses import MISSING, asdict, fields
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


_POSITIVE = {(PrinterProfile, "watts")}
_CHOICES = {(Settings, "theme"): ("system", "light", "dark")}


def _valid(cls, name: str, ftype: str, v) -> bool:
    """Is `v` an acceptable value for field `name` (annotated `ftype`) of `cls`?"""
    if ftype in ("float", "int"):
        if isinstance(v, bool) or not isinstance(v, (int, float) if ftype == "float" else int):
            return False
        if ftype == "int":
            return True
        return math.isfinite(v) and (v > 0 if (cls, name) in _POSITIVE else v >= 0)
    if ftype == "str":
        return isinstance(v, str) and v in _CHOICES.get((cls, name), (v,))
    if ftype == "bool":
        return isinstance(v, bool)
    if ftype == "list[str]":
        return isinstance(v, list) and all(isinstance(x, str) for x in v)
    return True


def _build_checked(cls, d, strict: bool, where: str):
    """Construct `cls` from `d` with type/range-checked values.

    Lenient: an invalid value takes the field default; an entry whose required
    field is invalid is dropped (returns None). Strict: raise ValueError.
    Missing required keys raise TypeError, as with `_build`.
    """
    if not isinstance(d, dict):
        if strict:
            raise ValueError(f"{where}: must be an object")
        return None
    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        if f.name not in d:
            continue
        v = d[f.name]
        if _valid(cls, f.name, f.type, v):
            kwargs[f.name] = float(v) if f.type == "float" else v
        elif strict:
            raise ValueError(f"{where}{f.name}: invalid value {v!r}")
        elif f.default is MISSING and f.default_factory is MISSING:
            return None
    return cls(**kwargs)


def _entries(d: dict, key: str, cls, strict: bool) -> list:
    raw = d.get(key, [])
    if not isinstance(raw, list):
        if strict:
            raise ValueError(f"{key}: must be a list")
        return []
    built = (_build_checked(cls, e, strict, f"{key}[{i}].") for i, e in enumerate(raw))
    return [e for e in built if e is not None]


def settings_to_dict(s: Settings) -> dict:
    return asdict(s)


def settings_from_dict(d: dict, strict: bool = False) -> Settings:
    return _build_checked(Settings, d, strict, "") or Settings()


def catalog_to_dict(c: Catalog) -> dict:
    return asdict(c)


def catalog_from_dict(d: dict, strict: bool = False) -> Catalog:
    return Catalog(
        printers=_entries(d, "printers", PrinterProfile, strict),
        filaments=_entries(d, "filaments", Filament, strict),
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
