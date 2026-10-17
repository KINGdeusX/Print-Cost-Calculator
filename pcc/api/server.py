"""FastAPI application (spec 8.2)."""

from __future__ import annotations

import hmac
import os
import tempfile
from pathlib import Path
from typing import Any, Literal

from fastapi import Body, Depends, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from pcc import __version__
from pcc.api.schemas import QuoteRequest
from pcc.core.jobs import build_job_from_project, project_to_dict
from pcc.core.models import FilamentUse, Job, Plate, new_id, new_job
from pcc.core.pricing import PricingError, compute_quote
from pcc.core.serialize import (
    catalog_from_dict, catalog_to_dict, quote_to_dict, settings_from_dict,
    settings_to_dict,
)
from pcc.core.storage import load_state, save_catalog, save_settings
from pcc.core.threemf import ThreeMFError, parse_3mf

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_HTTP_CODES = {404: "not_found", 405: "method_not_allowed", 403: "forbidden"}


_SLACK = 1024 * 1024  # multipart framing overhead


class BodyLimitMiddleware:
    """Reject request bodies over the cap, by Content-Length or bytes received."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return
        limit = MAX_UPLOAD_BYTES + _SLACK
        length = dict(scope["headers"]).get(b"content-length", b"")
        if length.isdigit() and int(length) > limit:
            await self._reject(scope, receive, send)
            return
        seen = 0
        tripped = False

        async def counting_receive():
            nonlocal seen, tripped
            if tripped:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    tripped = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            if not tripped:  # drop whatever the app answers once we cut the body
                await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except Exception:
            if not tripped:
                raise
        if tripped:
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope, receive, send):
        response = _error(413, "too_large", "Upload exceeds the 50 MB limit.")
        await response(scope, receive, send)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"code": code, "message": message}}
    )


def _read_upload(file: UploadFile) -> bytes:
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(413, "too_large", "Upload exceeds the 50 MB limit.")
    return data


def create_app(config_directory: Path | None = None) -> FastAPI:
    admin_token = os.environ.get("PCC_ADMIN_TOKEN") or ""
    origins = [
        o.strip() for o in os.environ.get("PCC_CORS_ORIGINS", "").split(",") if o.strip()
    ]
    state = load_state(config_directory, legacy_paths=[])

    app = FastAPI(title="Print Cost Calculator API", version=__version__)
    app.state.settings, app.state.catalog = state.settings, state.catalog
    app.add_middleware(BodyLimitMiddleware)  # inner; CORS added after is outermost
    if origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=origins,
            allow_methods=["*"], allow_headers=["*"],
        )

    @app.exception_handler(ApiError)
    async def _api_error(_r: Request, e: ApiError):
        return _error(e.status, e.code, e.message)

    @app.exception_handler(RequestValidationError)
    async def _validation(_r: Request, e: RequestValidationError):
        parts = [
            f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()
        ]
        return _error(422, "invalid_request", "; ".join(parts) or "Invalid request.")

    @app.exception_handler(Exception)
    async def _unhandled(_r: Request, _e: Exception):
        return _error(500, "internal_error", "Internal server error")

    @app.exception_handler(StarletteHTTPException)
    async def _http(_r: Request, e: StarletteHTTPException):
        code = _HTTP_CODES.get(e.status_code, "invalid_request" if e.status_code < 500 else "error")
        return _error(e.status_code, code, str(e.detail))

    def is_admin(request: Request) -> bool:
        if not admin_token:
            return False
        header = request.headers.get("authorization", "")
        scheme, _, supplied = header.partition(" ")
        if scheme.lower() != "bearer":
            return False
        return hmac.compare_digest(supplied.strip().encode(), admin_token.encode())

    def require_admin(request: Request) -> None:
        if not is_admin(request):
            raise ApiError(403, "forbidden", "Admin access required.")

    def pick_view(request: Request, view: str) -> Literal["public", "internal"]:
        if view == "internal":
            require_admin(request)
            return "internal"
        return "public"

    ViewQuery = Query("public", pattern="^(public|internal)$")

    # ---- public -------------------------------------------------------
    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/v1/printers")
    def printers():
        return [{"id": p.id, "name": p.name} for p in app.state.catalog.printers]

    @app.get("/api/v1/filaments")
    def filaments():
        return [
            {"id": f.id, "name": f.name, "type": f.type, "color": f.color}
            for f in app.state.catalog.filaments
        ]

    def parse_upload(file: UploadFile):
        try:
            return parse_3mf(_read_upload(file), file.filename or None)
        except ThreeMFError as e:
            raise ApiError(400, "invalid_3mf", str(e)) from None

    @app.post("/api/v1/parse")
    def parse(file: UploadFile = File(...)):
        return project_to_dict(parse_upload(file))

    def price(job: Job):
        try:
            return compute_quote(job, app.state.settings, app.state.catalog)
        except PricingError as e:
            raise ApiError(400, "pricing_error", str(e)) from None

    def job_from_request(body: QuoteRequest, admin: bool) -> Job:
        settings, catalog = app.state.settings, app.state.catalog
        printer_id = body.printer_id or catalog.default_printer().id
        packaging = (
            body.packaging if admin and body.packaging is not None
            else settings.default_packaging
        )
        labor = body.labor if admin and body.labor is not None else settings.default_labor
        if not admin and any(
            p.hours == 0 and sum(u.grams for u in p.filaments) == 0 for p in body.plates
        ):  # a zero plate prices only the fixed fees: don't let the public probe them
            raise ApiError(400, "invalid_request", "Each plate needs print time or filament")
        job = new_job(printer_id, packaging, body.customer)
        job.plates = [
            Plate(
                id=new_id("plate"), name=p.name, hours=p.hours, copies=p.copies,
                labor=labor,
                filaments=[
                    FilamentUse(filament_id=u.filament_id, grams=u.grams)
                    for u in p.filaments
                ],
            )
            for p in body.plates
        ]
        return job

    @app.post("/api/v1/quote")
    def quote(request: Request, body: QuoteRequest, view: str = ViewQuery):
        v = pick_view(request, view)
        job = job_from_request(body, is_admin(request))
        return quote_to_dict(price(job), v)

    @app.post("/api/v1/quote/3mf")
    def quote_3mf(
        request: Request,
        file: UploadFile = File(...),
        printer_id: str | None = Form(None),
        copies: int = Form(1, ge=1),
        customer: str = Form(""),
        view: str = ViewQuery,
    ):
        v = pick_view(request, view)
        project = parse_upload(file)
        try:
            job = build_job_from_project(
                project, app.state.settings, app.state.catalog,
                printer_id or None, copies, customer,
            )
        except PricingError as e:
            raise ApiError(400, "pricing_error", str(e)) from None
        return quote_to_dict(price(job), v)

    # ---- admin --------------------------------------------------------
    @app.post("/api/v1/export/xlsx", dependencies=[Depends(require_admin)])
    def export_xlsx(body: QuoteRequest):
        from pcc.core.export_xlsx import export_quote

        job = job_from_request(body, True)
        q = price(job)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quote.xlsx"
            export_quote(path, job, q, app.state.catalog, False)
            data = path.read_bytes()
        return Response(
            content=data, media_type=_XLSX,
            headers={"Content-Disposition": f'attachment; filename="quote-{job.id}.xlsx"'},
        )

    @app.get("/api/v1/admin/settings", dependencies=[Depends(require_admin)])
    def get_settings():
        return settings_to_dict(app.state.settings)

    @app.put("/api/v1/admin/settings", dependencies=[Depends(require_admin)])
    def put_settings(body: Any = Body(...)):
        if not isinstance(body, dict):
            raise ApiError(400, "invalid_request", "Settings must be a JSON object.")
        try:
            new = settings_from_dict(body, strict=True)
        except (TypeError, ValueError) as e:
            raise ApiError(400, "invalid_request", f"Invalid settings: {e}") from None
        save_settings(new, config_directory)
        app.state.settings = new
        return settings_to_dict(new)

    @app.get("/api/v1/admin/catalog", dependencies=[Depends(require_admin)])
    def get_catalog():
        return catalog_to_dict(app.state.catalog)

    @app.put("/api/v1/admin/catalog", dependencies=[Depends(require_admin)])
    def put_catalog(body: Any = Body(...)):
        if not isinstance(body, dict):
            raise ApiError(400, "invalid_request", "Catalog must be a JSON object.")
        try:
            new = catalog_from_dict(body, strict=True)
        except (TypeError, ValueError, AttributeError) as e:
            raise ApiError(400, "invalid_request", f"Invalid catalog: {e}") from None
        if not new.printers or not new.filaments:
            raise ApiError(
                400, "invalid_request",
                "Catalog needs at least one printer and one filament.",
            )
        save_catalog(new, config_directory)
        app.state.catalog = new
        return catalog_to_dict(new)

    return app


def run(host: str, port: int) -> None:
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)
