"""Pydantic request models for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FilamentUseIn(BaseModel):
    filament_id: str
    grams: float = Field(ge=0)


class PlateIn(BaseModel):
    name: str
    hours: float = Field(ge=0)
    copies: int = Field(default=1, ge=1)
    filaments: list[FilamentUseIn]


class QuoteRequest(BaseModel):
    customer: str = ""
    printer_id: str | None = None
    plates: list[PlateIn]
    labor: float | None = Field(default=None, ge=0)
    packaging: float | None = Field(default=None, ge=0)
