"""Locale-independent date text (`%b` follows the C locale, which Qt sets)."""
from __future__ import annotations

import datetime

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def short_date(d: datetime.date) -> str:
    """'19 Oct 2026' in English whatever the system locale."""
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"
