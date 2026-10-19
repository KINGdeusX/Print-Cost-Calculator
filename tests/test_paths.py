from pcc.core.paths import data_root, invoices_dir, linux_documents_dir, projects_dir
from pcc.core.serialize import settings_from_dict


def test_data_root_env(data_dir):
    assert data_root() == data_dir


def test_projects_and_invoices_dirs_created(data_dir):
    assert projects_dir() == data_dir / "Projects" and projects_dir().is_dir()
    assert invoices_dir() == data_dir / "Invoices" and invoices_dir().is_dir()


def test_linux_user_dirs_parsing(tmp_path):
    text = '# comment\nXDG_DOCUMENTS_DIR="$HOME/Dokumente"\n'
    assert linux_documents_dir(tmp_path, text) == tmp_path / "Dokumente"


def test_linux_fallback(tmp_path):
    assert linux_documents_dir(tmp_path, None) == tmp_path / "Documents"
    assert linux_documents_dir(tmp_path, 'XDG_DOCUMENTS_DIR="$HOME/"\n') == tmp_path / "Documents"


def test_settings_new_fields_defaults_and_lenient():
    s = settings_from_dict({"next_invoice_number": "x", "company_name": "Acme"})
    assert s.next_invoice_number == 1 and s.company_name == "Acme"
    assert settings_from_dict({"next_invoice_number": 0}).next_invoice_number == 1
    assert settings_from_dict({"next_invoice_number": 7}).next_invoice_number == 7
