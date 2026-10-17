from copy import deepcopy

import pytest
from pytest import approx

from pcc.core.models import FilamentUse, Filament, Plate
from pcc.core.pricing import PricingError, compute_quote, round_to_step


def test_reference_job(job, settings, catalog):
    q = compute_quote(job, settings, catalog)
    pb = q.plates[0]
    assert pb.per_copy.filament == approx(33.6)
    assert pb.per_copy.electricity == approx(5.46)
    assert pb.per_copy.failure == approx(3.906)
    assert pb.cost == approx(62.966)
    assert pb.price == approx(124.449)
    assert pb.price_total == approx(248.898)
    assert q.job_cost == approx(145.932)
    assert q.price_raw == approx(278.898)
    assert q.price == 280
    assert q.markup == approx(134.068)
    assert q.internal_fee == approx(60)
    assert q.total_hours == approx(7.0) and q.total_grams == approx(84.0)
    assert q.currency_symbol == "₱" and q.lines.filament == approx(67.2)


def test_round_half_up():
    assert round_to_step(277.5, 5) == 280
    assert round_to_step(12.5, 5) == 15
    assert round_to_step(1.005, 0) == 1.01


def test_failure_excludes_labor(job, settings, catalog):
    job.plates[0].labor = 100
    settings.failure_pct = 50
    pb = compute_quote(job, settings, catalog).plates[0]
    assert pb.per_copy.failure == approx(0.5 * (pb.per_copy.filament + pb.per_copy.electricity))


def test_packaging_charged_once(job, settings, catalog):
    base = compute_quote(job, settings, catalog).job_cost
    job.plates.append(deepcopy(job.plates[0]))
    q = compute_quote(job, settings, catalog)
    assert q.job_cost == approx(base + 2 * 62.966)
    assert q.packaging == 20


def test_multi_filament_plate(job, settings, catalog):
    catalog.filaments.append(Filament("pet", "PETG", "PETG", 1000.0))
    job.plates[0].filaments = [FilamentUse("pla", 40), FilamentUse("pet", 10)]
    assert compute_quote(job, settings, catalog).plates[0].per_copy.filament == approx(42.0)


def test_zero_margin_zero_fee_step0(job, settings, catalog):
    settings.margin_pct = 0
    settings.hidden_plate_fee = 0
    settings.rounding_step = 0
    q = compute_quote(job, settings, catalog)
    assert q.price == round(q.job_cost, 2)


@pytest.mark.parametrize("mutate", [
    lambda j, c: setattr(j.plates[0], "copies", 0),
    lambda j, c: setattr(j.plates[0].filaments[0], "grams", -1),
    lambda j, c: setattr(j.plates[0].filaments[0], "filament_id", "nope"),
    lambda j, c: setattr(j, "printer_id", "nope"),
])
def test_invalid_inputs_raise(job, settings, catalog, mutate):
    mutate(job, catalog)
    with pytest.raises(PricingError):
        compute_quote(job, settings, catalog)
