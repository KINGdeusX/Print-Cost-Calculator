"""Builds synthetic sliced .3mf files for tests."""

from __future__ import annotations

import io
import json
import struct
import zipfile
import zlib
from xml.sax.saxutils import quoteattr


def _png_1x1() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\xff\xff")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def build_3mf(
    plates: list[dict],
    project_settings: dict | None = None,
    model_settings_names: dict[int, str] | None = None,
    thumbnails: bool = True,
) -> bytes:
    lines = [
        "<config>",
        '  <header><header_item key="X-BBL-Client-Type" value="slicer"/></header>',
    ]
    for pl in plates:
        lines.append("  <plate>")
        lines.append(f'    <metadata key="index" value="{pl["index"]}"/>')
        lines.append(f'    <metadata key="prediction" value="{pl["prediction"]}"/>')
        lines.append(f'    <metadata key="weight" value="{pl["weight"]:.2f}"/>')
        for f in pl.get("filaments", []):
            used_g = float(f["used_g"])
            used_m = used_g / 3.0
            lines.append(
                f'    <filament id="{f["id"]}" type={quoteattr(f["type"])} '
                f'color={quoteattr(f["color"])} used_m="{used_m:.2f}" used_g="{used_g:.2f}"/>'
            )
        lines.append("  </plate>")
    lines.append("</config>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Metadata/slice_info.config", "\n".join(lines))
        if project_settings is not None:
            z.writestr("Metadata/project_settings.config", json.dumps(project_settings))
        if model_settings_names:
            ms = ["<config>"]
            for n, name in model_settings_names.items():
                ms.append(
                    f'  <plate><metadata key="plater_id" value="{n}"/>'
                    f'<metadata key="plater_name" value={quoteattr(name)}/></plate>'
                )
            ms.append("</config>")
            z.writestr("Metadata/model_settings.config", "\n".join(ms))
        if thumbnails:
            png = _png_1x1()
            for pl in plates:
                z.writestr(f"Metadata/plate_{pl['index']}.png", png)
    return buf.getvalue()


MULTI_PLATE_PROJECT: bytes = build_3mf(
    [
        {
            "index": 1,
            "prediction": 12300,
            "weight": 45.1,
            "filaments": [
                {"id": 1, "type": "PLA", "color": "#FFFFFF", "used_g": 42.1},
                {"id": 2, "type": "PETG", "color": "#000000", "used_g": 3.0},
            ],
        },
        {
            "index": 2,
            "prediction": 3600,
            "weight": 18,
            "filaments": [{"id": 1, "type": "PLA", "color": "#FFFFFF", "used_g": 18}],
        },
    ],
    project_settings={
        "printer_model": "Bambu Lab P1S",
        "printer_settings_id": "Bambu Lab P1S 0.4 nozzle",
        "filament_settings_id": ["Bambu PLA Basic @BBL P1S", "Generic PETG HF @BBL P1S"],
    },
)
