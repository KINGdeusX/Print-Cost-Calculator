"""Data model for the print cost calculator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


@dataclass
class PrinterProfile:
    id: str
    name: str
    watts: float
    model_match: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Filament:
    id: str
    name: str
    type: str
    price_per_kg: float
    color: str = "#808080"
    is_default: bool = False


@dataclass
class FilamentUse:
    filament_id: str
    grams: float
    slot: int | None = None
    source_type: str | None = None
    source_name: str | None = None
    source_color: str | None = None
    match: str = "manual"  # "exact" | "type" | "default" | "manual"


@dataclass
class Plate:
    id: str
    name: str
    hours: float
    filaments: list[FilamentUse]
    labor: float = 0.0
    copies: int = 1
    source_file: str | None = None
    plate_index: int | None = None
    thumbnail_png: bytes | None = None  # not persisted


@dataclass
class Job:
    id: str
    created_at: datetime
    customer: str = ""
    printer_id: str = ""
    plates: list[Plate] = field(default_factory=list)
    packaging: float = 0.0


def new_job(
    printer_id: str,
    packaging: float,
    customer: str = "",
    now: datetime | None = None,
) -> Job:
    now = now or datetime.now()
    return Job(
        id=now.strftime("%Y%m%d-%H%M%S"),
        created_at=now,
        customer=customer,
        printer_id=printer_id,
        plates=[],
        packaging=packaging,
    )


@dataclass
class Settings:
    schema_version: int = 2
    currency_code: str = "PHP"
    currency_symbol: str = "₱"
    electricity_rate: float = 12.0
    default_labor: float = 0.0
    default_packaging: float = 20.0
    margin_pct: float = 50.0  # percentage, 50 means 50 %
    failure_pct: float = 0.0  # percentage
    hidden_plate_fee: float = 0.0
    rounding_step: float = 5.0
    theme: str = "system"  # "system" | "light" | "dark"
    last_printer_id: str = ""
    last_export_path: str = ""
    window_geometry: str = ""  # base64


@dataclass
class Catalog:
    printers: list[PrinterProfile] = field(default_factory=list)
    filaments: list[Filament] = field(default_factory=list)

    def printer(self, id: str) -> PrinterProfile | None:
        return next((p for p in self.printers if p.id == id), None)

    def filament(self, id: str) -> Filament | None:
        return next((f for f in self.filaments if f.id == id), None)

    def default_filament(self) -> Filament:
        return next((f for f in self.filaments if f.is_default), self.filaments[0])

    def default_printer(self) -> PrinterProfile:
        return self.printers[0]

    def can_delete_printer(self, id: str) -> bool:
        return len(self.printers) > 1 and self.printer(id) is not None

    def can_delete_filament(self, id: str) -> bool:
        return len(self.filaments) > 1 and self.filament(id) is not None

    def set_default_filament(self, id: str) -> None:
        for f in self.filaments:
            f.is_default = f.id == id
