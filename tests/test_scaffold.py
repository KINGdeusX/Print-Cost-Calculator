import subprocess
import sys

import pytest


def test_version():
    import pcc

    assert pcc.__version__ == "0.3.0"


def test_core_and_cli_are_framework_free():
    code = ("import sys, pcc.core.models, pcc.core.pricing, pcc.core.serialize, "
            "pcc.core.storage, pcc.core.threemf, pcc.core.matching, pcc.core.export_xlsx, pcc.core.paths, pcc.core.projects, pcc.core.invoice, pcc.cli;"
            "bad=[m for m in ('PySide6','fastapi','pydantic','openpyxl') if m in sys.modules];"
            "print(','.join(bad))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ""
