import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from pcc.api.server import create_app
from tests.fixtures.make3mf import MULTI_PLATE_PROJECT

TOKEN = "s3cret-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
Q = "/api/v1/quote"
BODY = {
    "customer": "Niño 🎉 Café",
    "printer_id": None,
    "plates": [{"name": "A", "hours": 2.0, "copies": 2,
                "filaments": [{"filament_id": "pla", "grams": 30.0}]}],
}


def _client(cfg_dir, monkeypatch, token=TOKEN, cors=None):
    if token is None:
        monkeypatch.delenv("PCC_ADMIN_TOKEN", raising=False)
    else:
        monkeypatch.setenv("PCC_ADMIN_TOKEN", token)
    if cors:
        monkeypatch.setenv("PCC_CORS_ORIGINS", cors)
    else:
        monkeypatch.delenv("PCC_CORS_ORIGINS", raising=False)
    return TestClient(create_app(cfg_dir))


@pytest.fixture
def client(cfg_dir, monkeypatch):
    return _client(cfg_dir, monkeypatch, token=None)


@pytest.fixture
def admin_client(cfg_dir, monkeypatch):
    return _client(cfg_dir, monkeypatch)


def _upload(c, **kw):
    return c.post(Q + "/3mf", files={"file": ("p.3mf", MULTI_PLATE_PROJECT)}, **kw)


def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok", "version": "0.2.0"}


def test_filaments_public_has_no_price(client):
    items = client.get("/api/v1/filaments").json()
    assert "price_per_kg" not in items[0]
    assert set(items[0]) == {"id", "name", "type", "color"}


def test_printers_public(client):
    items = client.get("/api/v1/printers").json()
    assert set(items[0]) == {"id", "name"}


def test_parse(client):
    r = client.post("/api/v1/parse", files={"file": ("p.3mf", MULTI_PLATE_PROJECT)})
    d = r.json()
    assert r.status_code == 200 and len(d["plates"]) == 2
    assert "thumbnail_png" not in r.text and "price" not in r.text


def test_quote_3mf_public(client):
    r = _upload(client)
    assert r.status_code == 200 and "internal_fee" not in r.text and "markup" not in r.text
    assert len(r.json()["plates"]) == 2


def test_quote_3mf_copies(client):
    r = _upload(client, data={"copies": "3", "customer": "x"})
    assert r.json()["total_copies"] == 6


def test_internal_view_requires_admin(client, admin_client):
    assert _upload(admin_client, params={"view": "internal"}).status_code == 403
    bad = {"Authorization": "Bearer nope"}
    assert _upload(admin_client, params={"view": "internal"}, headers=bad).status_code == 403
    r = _upload(admin_client, params={"view": "internal"}, headers=AUTH)
    assert r.status_code == 200 and "internal_fee" in r.json()
    assert _upload(client, params={"view": "internal"}, headers=AUTH).status_code == 403


def test_admin_routes_403_when_token_unset(client):
    for method, path in [("get", "/api/v1/admin/settings"), ("put", "/api/v1/admin/settings"),
                         ("get", "/api/v1/admin/catalog"), ("put", "/api/v1/admin/catalog"),
                         ("post", "/api/v1/export/xlsx")]:
        r = getattr(client, method)(path, headers=AUTH, **({} if method == "get" else {"json": {}}))
        assert r.status_code == 403, path
        assert r.json()["error"]["code"] == "forbidden"


def test_admin_routes_need_token(admin_client):
    assert admin_client.get("/api/v1/admin/settings").status_code == 403
    assert admin_client.get("/api/v1/admin/settings", headers=AUTH).status_code == 200


def test_json_quote_and_unknown_filament(client):
    r = client.post(Q, json=BODY)
    assert r.status_code == 200 and r.json()["total_copies"] == 2
    bad = {**BODY, "plates": [{**BODY["plates"][0],
                               "filaments": [{"filament_id": "nope", "grams": 1}]}]}
    r = client.post(Q, json=bad)
    assert r.status_code == 400 and r.json()["error"]["code"] == "pricing_error"
    r = client.post(Q, json={**BODY, "printer_id": "nope"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "pricing_error"


def test_validation_error_shape(client):
    r = client.post(Q, json={"plates": [{"name": "A", "hours": -1, "filaments": []}]})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"


def test_not_found_shape(client):
    r = client.get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_public_cannot_override_labor(admin_client):
    base = admin_client.post(Q + "?view=internal", json=BODY, headers=AUTH).json()["lines"]["labor"]
    body = {**BODY, "labor": 999, "packaging": 999}
    pub = admin_client.post(Q, json=body).json()
    anon = admin_client.post(Q, json=BODY).json()
    assert pub["price"] == anon["price"]
    adm = admin_client.post(Q + "?view=internal", json=body, headers=AUTH).json()
    assert adm["lines"]["labor"] == 999 * 2 and adm["packaging"] == 999 and base != 999


def test_bad_3mf_400(client):
    r = client.post(Q + "/3mf", files={"file": ("p.3mf", b"junk")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_3mf"
    r = client.post("/api/v1/parse", files={"file": ("p.3mf", b"junk")})
    assert r.json()["error"]["code"] == "invalid_3mf"


def test_unknown_printer_form(client):
    r = _upload(client, data={"printer_id": "nope"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "pricing_error"


def test_too_large(client, monkeypatch):
    import pcc.api.server as s

    monkeypatch.setattr(s, "MAX_UPLOAD_BYTES", 100)
    r = _upload(client)
    assert r.status_code == 413 and r.json()["error"]["code"] == "too_large"
    r = client.post(Q + "/3mf", content=b"x" * (1024 * 1024 + 500),
                    headers={"content-type": "multipart/form-data; boundary=x"})
    assert r.status_code == 413


def test_cors_header(cfg_dir, monkeypatch):
    c = _client(cfg_dir, monkeypatch, cors="https://a.example, https://b.example")
    r = c.get("/api/v1/health", headers={"Origin": "https://a.example"})
    assert r.headers["access-control-allow-origin"] == "https://a.example"
    r = c.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_no_cors_by_default(client):
    r = client.get("/api/v1/health", headers={"Origin": "https://a.example"})
    assert "access-control-allow-origin" not in r.headers


def test_openapi_lists_routes(client):
    spec = client.get("/openapi.json").json()
    assert "/api/v1/quote" in spec["paths"]
    assert spec["info"]["title"] == "Print Cost Calculator API"
    assert spec["info"]["version"] == "0.2.0"


def test_export_xlsx(admin_client):
    assert admin_client.post("/api/v1/export/xlsx", json=BODY).status_code == 403
    r = admin_client.post("/api/v1/export/xlsx", json=BODY, headers=AUTH)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert 'filename="quote-' in r.headers["content-disposition"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert "Jobs" in wb.sheetnames


def test_settings_get_put(admin_client, cfg_dir):
    s = admin_client.get("/api/v1/admin/settings", headers=AUTH).json()
    s["margin_pct"] = 10.0
    r = admin_client.put("/api/v1/admin/settings", json=s, headers=AUTH)
    assert r.status_code == 200 and r.json()["margin_pct"] == 10.0
    assert admin_client.get("/api/v1/admin/settings", headers=AUTH).json()["margin_pct"] == 10.0
    assert '"margin_pct": 10.0' in (cfg_dir / "settings.json").read_text(encoding="utf-8")
    # in-memory state replaced: quotes use the new margin
    assert admin_client.put("/api/v1/admin/settings", json=[1], headers=AUTH).status_code in (400, 422)


def test_catalog_get_put(admin_client, cfg_dir):
    cat = admin_client.get("/api/v1/admin/catalog", headers=AUTH).json()
    assert cat["filaments"][0]["price_per_kg"] > 0
    for bad in ({"printers": [], "filaments": cat["filaments"]},
                {"printers": cat["printers"], "filaments": []},
                {"printers": [{"bogus": 1}], "filaments": cat["filaments"]}):
        r = admin_client.put("/api/v1/admin/catalog", json=bad, headers=AUTH)
        assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_request"
    new = {"printers": cat["printers"][:1], "filaments": cat["filaments"][:1]}
    assert admin_client.put("/api/v1/admin/catalog", json=new, headers=AUTH).status_code == 200
    assert len(admin_client.get("/api/v1/printers").json()) == 1
    assert (cfg_dir / "catalog.json").exists()


def test_token_not_echoed(admin_client):
    r = admin_client.get("/api/v1/admin/settings", headers={"Authorization": "Bearer wrong"})
    assert TOKEN not in r.text and "wrong" not in r.text
