"""Command-line interface (stdlib only at import time)."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from pcc import __version__
from pcc.core.currency import format_money
from pcc.core.jobs import build_job_from_project, project_to_dict
from pcc.core.pricing import PricingError, compute_quote
from pcc.core.serialize import catalog_to_dict, dumps, quote_to_dict
from pcc.core.storage import load_state
from pcc.core.threemf import ThreeMFError, parse_3mf


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def _positive_int(text: str) -> int:
    try:
        n = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid int value: {text!r}") from None
    if n < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return n


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pcc", description="Print cost calculator")
    p.add_argument("--version", action="version", version=f"pcc {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    q = sub.add_parser("quote", help="price a sliced .3mf")
    q.add_argument("file")
    q.add_argument("--printer")
    q.add_argument("--copies", type=_positive_int)
    q.add_argument("--customer", default="")
    q.add_argument("--json", action="store_true")
    q.add_argument("--internal", action="store_true")
    q.add_argument("--export", metavar="REPORT.xlsx")
    q.add_argument("--append", action="store_true")

    pa = sub.add_parser("parse", help="show plates in a sliced .3mf")
    pa.add_argument("file")
    pa.add_argument("--json", action="store_true")

    for name in ("printers", "filaments"):
        s = sub.add_parser(name, help=f"list {name}")
        s.add_argument("--json", action="store_true")

    s = sub.add_parser("serve", help="run the HTTP API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    return p


def _cmd_quote(a) -> int:
    state = load_state()
    settings, catalog = state.settings, state.catalog
    project = parse_3mf(a.file)
    job = build_job_from_project(
        project, settings, catalog, a.printer, a.copies or 1, a.customer
    )
    quote = compute_quote(job, settings, catalog)

    if a.export:
        from pcc.core.export_xlsx import export_quote

        try:
            export_quote(Path(a.export), job, quote, catalog, a.append)
        except Exception as e:  # invalid workbook, locked file, ...
            _err(f"Could not write report: {e}")
            return 3

    view = "internal" if a.internal else "public"
    if a.json:
        print(dumps(quote_to_dict(quote, view)))
        return 0
    sym = quote.currency_symbol
    for p in quote.plates:
        print(f"{p.name} ×{p.copies}  {format_money(p.price_total, sym)}")
    if a.internal:
        ln = quote.lines
        print(f"Filament  {format_money(ln.filament, sym)}")
        print(f"Electricity  {format_money(ln.electricity, sym)}")
        print(f"Failure allowance  {format_money(ln.failure, sym)}")
        print(f"Labor  {format_money(ln.labor, sym)}")
        print(f"Packaging  {format_money(quote.packaging, sym)}")
        print(f"Job cost  {format_money(quote.job_cost, sym)}")
        print(f"Internal fee  {format_money(quote.internal_fee, sym)}")
    print(f"PRICE  {format_money(quote.price, sym)}")
    return 0


def _cmd_parse(a) -> int:
    project = parse_3mf(a.file)
    if a.json:
        data = project_to_dict(project)
        print(dumps(data))
        return 0
    for p in project.plates:
        fils = ", ".join(f"{f.type} {f.grams:.1f} g" for f in p.filaments)
        print(f"{p.index}  {p.name}  {p.hours:.2f} h  {fils}")
    return 0


def _cmd_list(a) -> int:
    catalog = load_state().catalog
    items = catalog_to_dict(catalog)[a.command]
    if a.json:
        print(dumps(items))
    elif a.command == "printers":
        for p in items:
            print(f"{p['id']}  {p['name']}  {p['watts']:g} W")
    else:
        for f in items:
            star = " *" if f["is_default"] else ""
            print(f"{f['id']}  {f['name']}  {f['type']}  {f['price_per_kg']:g}/kg{star}")
    return 0


def _cmd_serve(a) -> int:
    try:
        server = importlib.import_module("pcc.api.server")
    except ImportError:
        _err("API support not installed: pip install print-cost-calculator[api]")
        return 2
    server.run(a.host, a.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 2)
    handler = {
        "quote": _cmd_quote, "parse": _cmd_parse, "printers": _cmd_list,
        "filaments": _cmd_list, "serve": _cmd_serve,
    }[args.command]
    try:
        return handler(args)
    except PricingError as e:
        _err(str(e))
        return 2
    except (ThreeMFError, OSError) as e:
        _err(str(e))
        return 3
    except KeyboardInterrupt:
        return 130
