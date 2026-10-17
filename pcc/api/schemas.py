"""Pydantic request models for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FilamentUseIn(BaseModel):
    filament_id: str
    grams: float = Field(ge=0, allow_inf_nan=False)


class PlateIn(BaseModel):
    name: str
    hours: float = Field(ge=0, allow_inf_nan=False)
    copies: int = Field(default=1, ge=1, le=999)
    filaments: list[FilamentUseIn] = Field(max_length=50)


class QuoteRequest(BaseModel):
    customer: str = ""
    printer_id: str | None = None
    plates: list[PlateIn] = Field(min_length=1, max_length=200)
    labor: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    packaging: float | None = Field(default=None, ge=0, allow_inf_nan=False)
