"""Parser for sliced Bambu Studio / OrcaSlicer .3mf files."""

from __future__ import annotations

import io
import json
import zlib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO
from xml.etree import ElementTree as ET

MAX_ENTRY_BYTES = 50 * 1024 * 1024
_BAD_FILE = "Not a valid .3mf file."
_NO_SLICE = (
    "No slice data. In Bambu Studio/OrcaSlicer use 'Export plate sliced file' "
    "or 'Export all sliced files'."
)


class ThreeMFError(Exception):
    pass


@dataclass
class ParsedFilament:
    slot: int
    type: str
    color: str
    grams: float
    preset_name: str | None = None


@dataclass
class ParsedPlate:
    index: int
    name: str
    seconds: float
    filaments: list[ParsedFilament] = field(default_factory=list)
    thumbnail_png: bytes | None = None

    @property
    def hours(self) -> float:
        return self.seconds / 3600.0


@dataclass
class ParsedProject:
    source_name: str
    printer_model: str | None
    printer_settings_id: str | None
    plates: list[ParsedPlate]


def _num(value: str | None) -> float:
    try:
        n = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return n if n == n and abs(n) != float("inf") else 0.0


def _int(value: str | None) -> int:
    return int(_num(value))


def _stem(name: str) -> str:
    low = name.lower()
    for suffix in (".gcode.3mf", ".3mf"):
        if low.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _meta(plate: ET.Element) -> dict[str, str]:
    return {
        m.get("key", ""): m.get("value", "")
        for m in plate.findall("metadata")
    }


def _str_or_none(v) -> str | None:
    return v if isinstance(v, str) and v else None


def parse_3mf(
    source: str | Path | bytes | BinaryIO, source_name: str | None = None
) -> ParsedProject:
    if isinstance(source, (str, Path)):
        if source_name is None:
            source_name = Path(source).name
        fileobj: BinaryIO | str | Path = source
    elif isinstance(source, (bytes, bytearray)):
        fileobj = io.BytesIO(bytes(source))
    else:
        fileobj = source
    source_name = source_name or "model.3mf"

    try:
        zf = zipfile.ZipFile(fileobj)  # type: ignore[arg-type]
    except (zipfile.BadZipFile, OSError, ValueError, EOFError) as e:
        raise ThreeMFError(_BAD_FILE) from e

    with zf:
        if any(i.file_size > MAX_ENTRY_BYTES for i in zf.infolist()):
            raise ThreeMFError(_BAD_FILE)
        names = set(zf.namelist())

        def read(name: str) -> bytes | None:
            if name not in names:
                return None
            try:
                return zf.read(name)
            except (zipfile.BadZipFile, OSError, zlib.error, EOFError, RuntimeError) as e:
                raise ThreeMFError(_BAD_FILE) from e

        slice_raw = read("Metadata/slice_info.config")
        if slice_raw is None:
            raise ThreeMFError(_NO_SLICE)
        try:
            slice_root = ET.fromstring(slice_raw)
        except ET.ParseError as e:
            raise ThreeMFError(_BAD_FILE) from e

        settings: dict = {}
        raw = read("Metadata/project_settings.config")
        if raw is not None:
            try:
                parsed = json.loads(raw.decode("utf-8-sig"))
                if isinstance(parsed, dict):
                    settings = parsed
            except (ValueError, UnicodeDecodeError):
                settings = {}
        presets = settings.get("filament_settings_id")
        if not isinstance(presets, list):
            presets = []

        plater_names: dict[int, str] = {}
        raw = read("Metadata/model_settings.config")
        if raw is not None:
            try:
                for pl in ET.fromstring(raw).iter("plate"):
                    md = _meta(pl)
                    if md.get("plater_id") and md.get("plater_name"):
                        plater_names[_int(md["plater_id"])] = md["plater_name"]
            except ET.ParseError:
                pass

        stem = _stem(source_name)
        plates: list[ParsedPlate] = []
        for n, pl in enumerate(slice_root.iter("plate"), start=1):
            md = _meta(pl)
            index = _int(md["index"]) if md.get("index") else n
            filaments: list[ParsedFilament] = []
            for f in pl.findall("filament"):
                grams = _num(f.get("used_g"))
                if grams <= 0:
                    continue
                slot = _int(f.get("id"))
                preset = (
                    _str_or_none(presets[slot - 1]) if 1 <= slot <= len(presets) else None
                )
                filaments.append(
                    ParsedFilament(
                        slot=slot,
                        type=f.get("type", ""),
                        color=f.get("color", ""),
                        grams=grams,
                        preset_name=preset,
                    )
                )
            if not filaments:
                continue
            name = md.get("plate_name") or plater_names.get(index) or f"{stem} · Plate {index}"
            plates.append(
                ParsedPlate(
                    index=index,
                    name=name,
                    seconds=_num(md.get("prediction")),
                    filaments=filaments,
                    thumbnail_png=read(f"Metadata/plate_{index}.png"),
                )
            )

    if not plates:
        raise ThreeMFError(_NO_SLICE)
    plates.sort(key=lambda p: p.index)
    return ParsedProject(
        source_name=source_name,
        printer_model=_str_or_none(settings.get("printer_model")),
        printer_settings_id=_str_or_none(settings.get("printer_settings_id")),
        plates=plates,
    )
