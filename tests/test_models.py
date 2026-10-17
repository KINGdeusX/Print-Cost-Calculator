from datetime import datetime

from pcc.core.currency import CURRENCIES, excel_money_format, format_money
from pcc.core.models import Catalog, Filament, PrinterProfile, Settings, new_id, new_job


def _fil(i, default=False):
    return Filament(id=i, name=i, type="PLA", price_per_kg=800, is_default=default)


def test_catalog_last_items_cannot_be_deleted():
    c = Catalog([PrinterProfile("p1", "P", 100)], [_fil("a")])
    assert not c.can_delete_printer("p1")
    assert not c.can_delete_filament("a")
    c.printers.append(PrinterProfile("p2", "Q", 100))
    c.filaments.append(_fil("b"))
    assert c.can_delete_printer("p1") and c.can_delete_filament("a")


def test_default_filament_fallback():
    c = Catalog([PrinterProfile("p1", "P", 100)], [_fil("a"), _fil("b")])
    assert c.default_filament().id == "a"
    c.set_default_filament("b")
    assert [f.is_default for f in c.filaments] == [False, True]
    assert c.default_filament().id == "b"
    c.set_default_filament("a")
    assert [f.is_default for f in c.filaments] == [True, False]


def test_lookups_and_defaults():
    c = Catalog([PrinterProfile("p1", "P", 100)], [_fil("a")])
    assert c.printer("p1").name == "P" and c.printer("x") is None
    assert c.filament("a").id == "a" and c.filament("x") is None
    assert c.default_printer().id == "p1"


def test_new_id_and_job():
    assert new_id("fil").startswith("fil-") and len(new_id("fil")) == 12
    j = new_job("p1", 20.0, now=datetime(2026, 10, 17, 9, 5, 7))
    assert j.id == "20261017-090507" and j.packaging == 20.0 and j.plates == []


def test_settings_defaults():
    s = Settings()
    assert (s.currency_code, s.currency_symbol, s.schema_version) == ("PHP", "₱", 2)
    assert (s.electricity_rate, s.default_labor, s.default_packaging) == (12, 0, 20)
    assert (s.margin_pct, s.failure_pct, s.hidden_plate_fee, s.rounding_step) == (50, 0, 0, 5)
    assert s.theme == "system"


def test_format_money():
    assert format_money(1025, "₱") == "₱1,025.00"
    assert format_money(-5, "€") == "-€5.00"
    assert excel_money_format("₱") == '"₱"#,##0.00'


def test_currencies_listed():
    codes = {c[0]: c[1] for c in CURRENCIES}
    for code, sym in [("PHP", "₱"), ("USD", "$"), ("EUR", "€"), ("GBP", "£"), ("JPY", "¥"),
                      ("AUD", "A$"), ("CAD", "C$"), ("SGD", "S$"), ("INR", "₹"),
                      ("IDR", "Rp"), ("MYR", "RM"), ("THB", "฿"), ("KRW", "₩"), ("CNY", "¥")]:
        assert codes[code] == sym
