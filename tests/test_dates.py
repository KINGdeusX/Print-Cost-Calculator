import datetime

import pytest

from pcc.core.dates import short_date

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@pytest.mark.parametrize("month", range(1, 13))
def test_short_date_english_months(month):
    assert short_date(datetime.date(2026, month, 3)) == f"3 {MONTHS[month - 1]} 2026"


def test_short_date_accepts_datetime():
    assert short_date(datetime.datetime(2026, 10, 19, 23, 59)) == "19 Oct 2026"


class _Localized(datetime.datetime):
    """Stands in for a C library running under a German LC_TIME (Qt calls setlocale)."""

    def strftime(self, fmt):
        return super().strftime(fmt.replace("%b", "Okt"))

    def __format__(self, fmt):
        return self.strftime(fmt) if fmt else str(self)


def test_invoice_date_ignores_c_locale():
    from pcc.gui.invoice_pdf import _fmt_date
    assert _fmt_date(_Localized(2026, 10, 19)) == "19 Oct 2026"


def test_list_edited_ignores_c_locale(monkeypatch):
    from pcc.gui.widgets import projects_page

    class _DT(datetime.datetime):
        @classmethod
        def fromisoformat(cls, s):
            d = datetime.datetime.fromisoformat(s)
            return _Localized(d.year, d.month, d.day)

    monkeypatch.setattr(projects_page, "datetime", _DT)
    assert projects_page._edited("2026-10-19T10:00:00") == "edited 19 Oct 2026"
    assert projects_page._edited("garbage") == ""
