import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture
def cfg_dir(tmp_path, monkeypatch):
    path = tmp_path / "cfg"
    monkeypatch.setenv("PCC_CONFIG_DIR", str(path))
    return path


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    path = tmp_path / "data"
    monkeypatch.setenv("PCC_DATA_DIR", str(path))
    return path


@pytest.fixture
def settings():
    from pcc.core.models import Settings

    return Settings(
        electricity_rate=12.0,
        margin_pct=50.0,
        failure_pct=10.0,
        hidden_plate_fee=30.0,
        rounding_step=5.0,
    )


@pytest.fixture
def catalog():
    from pcc.core.models import Catalog, Filament, PrinterProfile

    return Catalog(
        printers=[PrinterProfile(id="p1", name="Printer 1", watts=130.0)],
        filaments=[
            Filament(id="pla", name="PLA", type="PLA", price_per_kg=800.0, is_default=True)
        ],
    )


@pytest.fixture
def job():
    from datetime import datetime

    from pcc.core.models import FilamentUse, Job, Plate

    return Job(
        id="20261017-120000",
        created_at=datetime(2026, 10, 17, 12, 0, 0),
        printer_id="p1",
        packaging=20.0,
        plates=[
            Plate(
                id="A",
                name="A",
                hours=3.5,
                filaments=[FilamentUse(filament_id="pla", grams=42.0)],
                labor=20.0,
                copies=2,
            )
        ],
    )


@pytest.fixture
def quote(job, settings, catalog):
    from pcc.core.pricing import compute_quote

    return compute_quote(job, settings, catalog)


@pytest.fixture(autouse=True)
def _qt_teardown_guard():
    yield
    if "PySide6.QtWidgets" not in sys.modules:
        return
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    from pcc.gui import state as state_mod

    for st in list(state_mod._INSTANCES):
        try:
            st.shutdown()
        except RuntimeError:  # underlying C++ object already deleted
            pass
    if QApplication.instance() is not None:
        QApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
