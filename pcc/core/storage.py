"""Persistent settings/catalog storage, seed catalog and v0.1 migration."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pcc.core.models import Catalog, Filament, PrinterProfile, Settings
from pcc.core.serialize import (
    catalog_from_dict, catalog_to_dict, dumps, settings_from_dict,
    settings_to_dict,
)

_NOTE = "Indicative average — measure with a plug meter for accuracy."

# (model name, watts, model_match) — specific models precede their prefixes.
_BAMBU = [
    ("A1 mini", 80, ["A1 mini"]),
    ("A1", 100, ["A1"]),
    ("A2L", 100, ["A2L"]),
    ("P1P", 130, ["P1P"]),
    ("P1S", 130, ["P1S"]),
    ("P2S", 140, ["P2S"]),
    ("X1 Carbon", 140, ["X1 Carbon", "X1C"]),
    ("X1E", 160, ["X1E"]),
    ("X1", 140, ["X1"]),
    ("X2D", 170, ["X2D"]),
    ("H2S", 210, ["H2S"]),
    ("H2D Pro", 240, ["H2D Pro"]),
    ("H2D", 240, ["H2D"]),
    ("H2C", 240, ["H2C"]),
]

# (type, price multiplier)
_FILAMENTS = [
    ("PLA", 1.0), ("PETG", 1.0), ("ABS", 1.0), ("ASA", 1.0),
    ("TPU", 1.25), ("PLA-CF", 1.5),
]


def _slug(text: str) -> str:
    return "-".join(text.lower().split())


def config_dir() -> Path:
    env = os.environ.get("PCC_CONFIG_DIR")
    if env:
        return Path(env)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "PrintCostCalculator"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PrintCostCalculator"
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "print-cost-calculator"


def default_settings() -> Settings:
    return Settings()


def default_catalog(default_price: float = 800.0) -> Catalog:
    printers = [
        PrinterProfile(
            id=_slug(f"bambu {model}"), name=f"Bambu Lab {model}", watts=float(w),
            model_match=list(match), notes=_NOTE,
        )
        for model, w, match in _BAMBU
    ]
    printers.append(PrinterProfile(id="custom", name="Custom FDM", watts=150.0))
    filaments = [
        Filament(
            id=t.lower(), name=f"Generic {t}", type=t,
            price_per_kg=default_price * mult, is_default=(t == "PLA"),
        )
        for t, mult in _FILAMENTS
    ]
    return Catalog(printers=printers, filaments=filaments)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline="\n",
        prefix=path.name + ".", suffix=".tmp",
    )
    try:
        with tmp:
            tmp.write(text)
        os.replace(tmp.name, path)
    except BaseException:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def save_settings(settings: Settings, directory: Path | None = None) -> None:
    d = directory or config_dir()
    atomic_write_text(d / "settings.json", dumps(settings_to_dict(settings)))


def save_catalog(catalog: Catalog, directory: Path | None = None) -> None:
    d = directory or config_dir()
    atomic_write_text(d / "catalog.json", dumps(catalog_to_dict(catalog)))


@dataclass
class LoadResult:
    settings: Settings
    catalog: Catalog
    warnings: list[str] = field(default_factory=list)


def _backup(path: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.bak-{stamp}")
    n = 1
    while target.exists():
        target = path.with_name(f"{path.name}.bak-{stamp}-{n}")
        n += 1
    os.replace(path, target)


def _parse_catalog(data: dict) -> Catalog:
    c = catalog_from_dict(data)
    if not c.printers or not c.filaments:
        raise ValueError("empty catalog")
    return c


def _load_file(path: Path, parse, default, warnings: list[str]):
    if not path.exists():
        return default()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not an object")
        return parse(data)
    except (ValueError, KeyError, TypeError, OSError):  # JSON/Unicode errors are ValueErrors
        try:
            _backup(path)
        except OSError:
            pass
        warnings.append(
            f"{path.name} was unreadable; a backup was saved and defaults loaded."
        )
        return default()


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _read_legacy(paths: list[Path]) -> dict | None:
    for p in paths:
        try:
            if not p.is_file():
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _migrate(legacy: dict) -> tuple[Settings, Catalog]:
    s = default_settings()
    price = legacy.get("filament_cost")
    c = default_catalog(float(price)) if _num(price) else default_catalog()
    if _num(legacy.get("packaging")):
        s.default_packaging = float(legacy["packaging"])
    if _num(legacy.get("rate")):
        s.electricity_rate = float(legacy["rate"])
    if _num(legacy.get("margin")):
        s.margin_pct = float(legacy["margin"])
    if _num(legacy.get("power")):
        c.printers.insert(
            0, PrinterProfile(id="my-printer", name="My Printer",
                              watts=float(legacy["power"])),
        )
        s.last_printer_id = "my-printer"
    return s, c


def load_state(
    directory: Path | None = None, legacy_paths: list[Path] | None = None
) -> LoadResult:
    d = directory or config_dir()
    warnings: list[str] = []
    settings_path = d / "settings.json"
    if not settings_path.exists():
        if legacy_paths is None:
            legacy_paths = [
                Path(sys.executable).parent / "pricing_config.json",
                Path.cwd() / "pricing_config.json",
            ]
        legacy = _read_legacy(legacy_paths)
        if legacy is not None:
            s, c = _migrate(legacy)
            save_settings(s, d)
            save_catalog(c, d)
            return LoadResult(s, c, ["Imported settings from v0.1"])
    settings = _load_file(settings_path, settings_from_dict, default_settings, warnings)
    catalog = _load_file(d / "catalog.json", _parse_catalog, default_catalog, warnings)
    return LoadResult(settings, catalog, warnings)
