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


def _bump(unit: Decimal, qty: int, change: Decimal) -> Decimal:
    """New unit price after adding `change` to the line amount; never below 0."""
    return max(_ZERO, q2(unit + change / qty))


def build_invoice_lines(quote: Quote) -> list[InvoiceLine]:
    target = q2(quote.price)
    # [description, qty, unit]
    rows: list[list] = [[pb.name, pb.copies, q2(pb.price)] for pb in quote.plates]
    plate_count = len(rows)
    packaging = q2(
        Decimal(str(quote.price_raw)) - sum((Decimal(str(pb.price_total)) for pb in quote.plates), Decimal(0))
    )
    pack_idx = None
    if packaging > 0:
        rows.append(["Packaging", 1, packaging])
        pack_idx = len(rows) - 1

    def total() -> Decimal:
        return sum((r[1] * r[2] for r in rows), Decimal(0))

    # Spread the delta over plate lines proportionally to their amounts.
    delta = target - total()
    plate_sum = sum((r[1] * r[2] for r in rows[:plate_count]), Decimal(0))
    if delta != 0 and plate_sum > 0:
        for r in rows[:plate_count]:
            amount = r[1] * r[2]
            per_unit = _trunc(delta * amount / plate_sum / r[1])
            r[2] = max(_ZERO, r[2] + per_unit)

    # Remainder rule.
    rem = target - total()
    if rem != 0:
        if pack_idx is not None:
            r = rows[pack_idx]
            r[2] = max(_ZERO, r[2] + rem)
        else:
            singles = [r for r in rows[:plate_count] if r[1] == 1]
            if singles:
                best = max(singles, key=lambda r: r[2])
                best[2] = max(_ZERO, best[2] + rem)
        rem = target - total()
        if rem != 0:
            rows.append(["Rounding", 1, rem])

    return [InvoiceLine(d, q, u, q * u) for d, q, u in rows]


def invoice_total(lines: list[InvoiceLine]) -> Decimal:
    return sum((ln.amount for ln in lines), Decimal("0.00"))
