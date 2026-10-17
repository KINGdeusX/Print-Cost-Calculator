import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture
def cfg_dir(tmp_path, monkeypatch):
    path = tmp_path / "cfg"
    monkeypatch.setenv("PCC_CONFIG_DIR", str(path))
    return path
