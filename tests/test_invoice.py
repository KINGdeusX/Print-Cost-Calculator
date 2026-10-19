import random
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from pcc.core.invoice import InvoiceLine, build_invoice_lines, invoice_total, q2
from pcc.core.models import FilamentUse, Job, Plate
from pcc.core.pricing import compute_quote


def _rows(lines):
    return [(l.description, l.qty, l.unit_price, l.amount) for l in lines]


def _check(lines, quote):
    assert invoice_total(lines) == q2(quote.price)
    for l in lines:
        assert l.amount == l.unit_price * l.qty
        if l.description != "Rounding":
            assert l.unit_price >= 0


def test_reference_quote(quote):
    lines = build_invoice_lines(quote)
    assert _rows(lines) == [
        ("A", 2, Decimal("125.00"), Decimal("250.00")),
        ("Packaging", 1, Decimal("30.00"), Decimal("30.00")),
    ]
    assert invoice_total(lines) == Decimal("280.00")


def test_rounding_down(job, settings, catalog):
    # find a job whose rounded price is below the raw price (negative delta)
    for hours in [x / 10 for x in range(10, 80)]:
        j = replace(job, plates=[replace(job.plates[0], hours=hours)])
        q = compute_quote(j, settings, catalog)
        if q.price < q.price_raw - 0.5:
            lines = build_invoice_lines(q)
            _check(lines, q)
            return
    raise AssertionError("no rounding-down scenario found")


def test_step_zero(job, settings, catalog):
    q = compute_quote(job, replace(settings, rounding_step=0.0), catalog)
    lines = build_invoice_lines(q)
    _check(lines, q)
    assert invoice_total(lines) == q2(q.price)


def test_no_packaging_all_multi_copy_gets_rounding_line(job, settings, catalog):
    j = replace(job, packaging=0.0, plates=[replace(job.plates[0], copies=3)])
    for hours in [x / 10 for x in range(10, 60)]:
        j = replace(j, plates=[replace(j.plates[0], hours=hours)])
        q = compute_quote(j, settings, catalog)
        lines = build_invoice_lines(q)
        _check(lines, q)
        if any(l.description == "Rounding" for l in lines):
            assert lines[-1].description == "Rounding"
            return
    raise AssertionError("no Rounding line produced")


def test_remainder_prefers_qty1_plate(job, settings, catalog):
    j = replace(job, packaging=0.0, plates=[replace(job.plates[0], copies=1)])
    q = compute_quote(j, settings, catalog)
    lines = build_invoice_lines(q)
    _check(lines, q)
    assert [l.description for l in lines] == ["A"]


def test_invariants_random(job, settings, catalog):
    rng = random.Random(1234)
    for _ in range(300):
        plates = [
            Plate(
                id=f"P{i}", name=f"P{i}", hours=round(rng.uniform(0.1, 30), 2),
                filaments=[FilamentUse(filament_id="pla", grams=round(rng.uniform(1, 500), 1))],
                labor=round(rng.uniform(0, 100), 2), copies=rng.randint(1, 6),
            )
            for i in range(rng.randint(1, 4))
        ]
        j = replace(job, packaging=rng.choice([0.0, round(rng.uniform(0, 80), 2)]), plates=plates)
        s = replace(settings, rounding_step=rng.choice([0.0, 1.0, 5.0, 10.0]),
                    margin_pct=rng.choice([0.0, 30.0, 50.0]))
        q = compute_quote(j, s, catalog)
        _check(build_invoice_lines(q), q)
