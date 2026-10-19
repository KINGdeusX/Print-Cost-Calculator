from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QFileDialog

from pcc.core.paths import projects_dir
from pcc.gui import logo
from pcc.gui.dialogs import settings_dialog
from pcc.gui.dialogs.settings_dialog import SettingsDialog
from pcc.gui.state import AppState


def make_dialog(qtbot, **kw):
    state = AppState(legacy_paths=[])
    d = SettingsDialog(state, **kw)
    qtbot.addWidget(d)
    return state, d


def png(tmp_path, w=400, h=300, name="big.png"):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("red"))
    p = tmp_path / name
    assert img.save(str(p))
    return p


def pick(monkeypatch, path):
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(path), ""))


def test_company_name_saved(qtbot, cfg_dir, data_dir):
    state, d = make_dialog(qtbot)
    d.company_edit.setText("Acme 3D")
    assert d.changed_fields() == {"company_name": "Acme 3D"}
    d.accept()
    assert state.settings.company_name == "Acme 3D"


def test_logo_upload_accept_persists_jpeg(qtbot, cfg_dir, data_dir, tmp_path, monkeypatch):
    state, d = make_dialog(qtbot)
    assert d.logo_preview.text() == "No logo"
    pick(monkeypatch, png(tmp_path))
    d.logo_upload_button.click()
    assert not logo.logo_path().exists()  # nothing on disk before OK
    assert d.logo_preview.pixmap() is not None and not d.logo_preview.pixmap().isNull()
    assert d.logo_error_label.isHidden()
    d.accept()
    data = logo.read_logo()
    assert data is not None
    img = QImage.fromData(data)
    assert max(img.width(), img.height()) <= 150


def test_logo_cancel_discards(qtbot, cfg_dir, data_dir, tmp_path, monkeypatch):
    state, d = make_dialog(qtbot)
    pick(monkeypatch, png(tmp_path))
    d.logo_upload_button.click()
    d.reject()
    assert not logo.logo_path().exists()


def test_logo_remove(qtbot, cfg_dir, data_dir, tmp_path, monkeypatch):
    logo.save_logo(logo.load_logo_image(png(tmp_path)))
    state, d = make_dialog(qtbot)
    assert d.logo_remove_button.isEnabled()
    d.logo_remove_button.click()
    assert logo.logo_path().exists()  # deferred until OK
    assert d.logo_preview.text() == "No logo"
    assert not d.logo_remove_button.isEnabled()
    d.accept()
    assert not logo.logo_path().exists()


def test_remove_then_cancel_keeps_logo(qtbot, cfg_dir, data_dir, tmp_path):
    logo.save_logo(logo.load_logo_image(png(tmp_path)))
    state, d = make_dialog(qtbot)
    d.logo_remove_button.click()
    d.reject()
    assert logo.read_logo() is not None


def test_bad_image_shows_error_keeps_old(qtbot, cfg_dir, data_dir, tmp_path, monkeypatch):
    old = logo.load_logo_image(png(tmp_path))
    logo.save_logo(old)
    state, d = make_dialog(qtbot)
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    pick(monkeypatch, bad)
    d.show()
    d.logo_upload_button.click()
    assert d.logo_error_label.text() == "Couldn't read that image."
    assert d.logo_error_label.isVisible()
    assert not d.logo_preview.pixmap().isNull()  # old logo still shown
    d.accept()
    assert logo.read_logo() == old


def test_cancelled_file_dialog_is_noop(qtbot, cfg_dir, data_dir, monkeypatch):
    state, d = make_dialog(qtbot)
    pick(monkeypatch, "")
    d.logo_upload_button.click()
    assert d.logo_preview.text() == "No logo"
    assert d.logo_error_label.isHidden()


def test_data_folder_row(qtbot, cfg_dir, data_dir, monkeypatch):
    state, d = make_dialog(qtbot)
    assert d.data_folder_label.text() == str(projects_dir())
    opened = []
    monkeypatch.setattr(settings_dialog.QDesktopServices, "openUrl",
                        lambda url: opened.append(url) or True)
    d.open_data_folder_button.click()
    assert opened == [QUrl.fromLocalFile(str(projects_dir()))]


def test_company_section_is_first(qtbot, cfg_dir, data_dir):
    from PySide6.QtWidgets import QLabel
    state, d = make_dialog(qtbot)
    heads = [w.text() for w in d.findChildren(QLabel)
             if w.text() in ("🏢 Company", "⚡ Costs", "📈 Pricing", "🎨 Appearance")]
    assert heads[0] == "🏢 Company"


def test_focus_company(qtbot, cfg_dir, data_dir):
    state, d = make_dialog(qtbot, focus_company=True)
    d.show()
    qtbot.waitUntil(lambda: d.company_edit.hasFocus(), timeout=2000)
