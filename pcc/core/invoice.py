"""Invoice line maths: lines that sum exactly to the rounded quote price."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from pcc.core.pricing import Quote

_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")


def q2(value: Decimal | float | int | str) -> Decimal:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _trunc(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_DOWN)


@dataclass(frozen=True)
class InvoiceLine:
    description: str
    qty: int
    unit_price: Decimal
    amount: Decimal


@dataclass
class _Row:
    description: str
    qty: int
    unit: Decimal


def build_invoice_lines(quote: Quote) -> list[InvoiceLine]:
    """Build invoice lines whose amounts sum exactly to q2(quote.price).

    Item lines (plates, Packaging) never have a negative unit price. The
    delta between the rounded price and the summed lines is spread over the
    plates; the remainder goes to Packaging, else the largest qty-1 plate,
    else a signed "Rounding" line. That line may be NEGATIVE. It appears only
    when there is no Packaging line and no qty-1 plate (or when clamping at
    0 blocks absorption). Without clamping its magnitude is strictly less
    than 0.01 x (sum of plate quantities), because each per-unit spread
    truncates by less than 0.01.
    """
    target = q2(quote.price)
    rows: list[_Row] = [_Row(pb.name, pb.copies, q2(pb.price)) for pb in quote.plates]
    plate_count = len(rows)
    packaging = q2(
        Decimal(str(quote.price_raw)) - sum((Decimal(str(pb.price_total)) for pb in quote.plates), Decimal(0))
    )
    pack_idx = None
    if packaging > 0:
        rows.append(_Row("Packaging", 1, packaging))
        pack_idx = len(rows) - 1

    def total() -> Decimal:
        return sum((r.qty * r.unit for r in rows), Decimal(0))

    # Spread the delta over plate lines proportionally to their amounts.
    delta = target - total()
    plate_sum = sum((r.qty * r.unit for r in rows[:plate_count]), Decimal(0))
    if delta != 0 and plate_sum > 0:
        for r in rows[:plate_count]:
            amount = r.qty * r.unit
            per_unit = _trunc(delta * amount / plate_sum / r.qty)
            r.unit = max(_ZERO, r.unit + per_unit)

    # Remainder rule.
    rem = target - total()
    if rem != 0:
        if pack_idx is not None:
            r = rows[pack_idx]
            r.unit = max(_ZERO, r.unit + rem)
        else:
            singles = [r for r in rows[:plate_count] if r.qty == 1]
            if singles:
                best = max(singles, key=lambda r: r.unit)
                best.unit = max(_ZERO, best.unit + rem)
        rem = target - total()
        if rem != 0:
            rows.append(_Row("Rounding", 1, rem))

    return [InvoiceLine(r.description, r.qty, r.unit, r.qty * r.unit) for r in rows]


def invoice_total(lines: list[InvoiceLine]) -> Decimal:
    return sum((ln.amount for ln in lines), Decimal("0.00"))
