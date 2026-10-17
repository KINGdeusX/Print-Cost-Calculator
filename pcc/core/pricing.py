"""Pricing engine (spec section 5)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from pcc.core.models import Catalog, Job, Settings


class PricingError(ValueError):
    """Invalid pricing input."""


@dataclass(frozen=True)
class CostLines:
    filament: float
    electricity: float
    failure: float
    labor: float

    @property
    def total(self) -> float:
        return self.filament + self.electricity + self.failure + self.labor

    def scaled(self, k: float) -> "CostLines":
        return CostLines(self.filament * k, self.electricity * k, self.failure * k, self.labor * k)


@dataclass(frozen=True)
class PlateBreakdown:
    plate_id: str
    name: str
    copies: int
    hours: float
    grams: float
    per_copy: CostLines
    cost: float  # per copy
    price: float  # per copy
    cost_total: float
    price_total: float
    internal_fee_total: float


@dataclass(frozen=True)
class Quote:
    job_id: str
    currency_code: str
    currency_symbol: str
    plates: list[PlateBreakdown]
    lines: CostLines  # x copies
    packaging: float
    job_cost: float
    price_raw: float
    price: float
    markup: float
    internal_fee: float
    total_hours: float
    total_grams: float
    total_copies: int


def round_to_step(value: float, step: float) -> float:
    d = Decimal(str(value))
    if step <= 0:
        return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    s = Decimal(str(step))
    return float((d / s).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * s)


def _nonneg(value: float, what: str) -> None:
    if value < 0:
        raise PricingError(f"{what} must not be negative.")


def compute_quote(job: Job, settings: Settings, catalog: Catalog) -> Quote:
    printer = catalog.printer(job.printer_id)
    if printer is None:
        raise PricingError(f"Unknown printer '{job.printer_id}'.")
    _nonneg(printer.watts, "Printer watts")
    _nonneg(job.packaging, "Packaging")
    _nonneg(settings.electricity_rate, "Electricity rate")
    _nonneg(settings.margin_pct, "Margin")
    _nonneg(settings.failure_pct, "Failure allowance")
    _nonneg(settings.hidden_plate_fee, "Hidden plate fee")
    m = settings.margin_pct / 100
    f = settings.failure_pct / 100
    h = settings.hidden_plate_fee

    plates: list[PlateBreakdown] = []
    totals = CostLines(0.0, 0.0, 0.0, 0.0)
    cost_sum = price_sum = fee = hours = grams = 0.0
    copies_sum = 0
    for p in job.plates:
        if p.copies < 1:
            raise PricingError(f"Plate '{p.name}': copies must be at least 1.")
        _nonneg(p.hours, f"Plate '{p.name}' hours")
        _nonneg(p.labor, f"Plate '{p.name}' labor")
        fil_cost = plate_grams = 0.0
        for u in p.filaments:
            fil = catalog.filament(u.filament_id)
            if fil is None:
                raise PricingError(f"Plate '{p.name}': unknown filament '{u.filament_id}'.")
            _nonneg(u.grams, f"Plate '{p.name}' grams")
            fil_cost += u.grams / 1000 * fil.price_per_kg
            plate_grams += u.grams
        elec = printer.watts / 1000 * p.hours * settings.electricity_rate
        per = CostLines(fil_cost, elec, (fil_cost + elec) * f, p.labor)
        cost = per.total
        price = cost * (1 + m) + h
        q = p.copies
        plates.append(PlateBreakdown(
            p.id, p.name, q, p.hours, plate_grams, per, cost, price,
            cost * q, price * q, h * q,
        ))
        s = per.scaled(q)
        totals = CostLines(
            totals.filament + s.filament, totals.electricity + s.electricity,
            totals.failure + s.failure, totals.labor + s.labor,
        )
        cost_sum += cost * q
        price_sum += price * q
        fee += h * q
        hours += p.hours * q
        grams += plate_grams * q
        copies_sum += q

    job_cost = cost_sum + job.packaging
    price_raw = price_sum + job.packaging * (1 + m)
    price = round_to_step(price_raw, settings.rounding_step)
    return Quote(
        job_id=job.id,
        currency_code=settings.currency_code,
        currency_symbol=settings.currency_symbol,
        plates=plates,
        lines=totals,
        packaging=job.packaging,
        job_cost=job_cost,
        price_raw=price_raw,
        price=price,
        markup=price - job_cost,
        internal_fee=fee,
        total_hours=hours,
        total_grams=grams,
        total_copies=copies_sum,
    )
