import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.controllers import router
from app.controllers.web_api import router as web_router
from app.core.config import settings
from app.core.database import create_db_and_tables, database_is_ready
from app.static_site import mount_static_site

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime()
    if settings.auto_create_tables: create_db_and_tables()
    if settings.debug_auth_enabled: logger.warning("DEBUG authentication is enabled; never deploy this setting")
    yield


app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix=settings.api_prefix)
app.include_router(web_router)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    detail = str(exc.detail)
    code = _error_code(exc.status_code, detail)
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": detail}})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    fields = {}
    for error in exc.errors():
        location = error.get("loc", ())
        field = str(location[-1]) if location else "request"
        fields[field] = error.get("msg", "Invalid value")
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_FAILED", "message": "Please fix the highlighted fields.", "fields": fields}},
    )


@app.get("/health", tags=["system"])
def health(): return {"status": "ok", "service": settings.app_name}


@app.get("/ready", tags=["system"])
def ready():
    if not database_is_ready():
        raise HTTPException(503, "Database is unavailable")
    return {"status": "ready"}


def _error_code(status_code: int, detail: str) -> str:
    lower = detail.lower()
    if status_code == 401:
        return "UNAUTHENTICATED"
    if status_code == 403:
        return "FORBIDDEN"
    if "invitation" in lower:
        return "INVITATION_INVALID"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 422:
        return "VALIDATION_FAILED"
    if "deadline" in lower or "not active" in lower:
        return "SESSION_CLOSED"
    if "no timeslot" in lower:
        return "NO_FEASIBLE_TIMESLOT"
    if "stale" in lower:
        return "RECOMMENDATIONS_STALE"
    if "feasible combination" in lower:
        return "COMBINATION_NOT_FEASIBLE"
    if "calendar is not connected" in lower:
        return "CALENDAR_NOT_CONNECTED"
    if status_code == 503:
        return "EXTERNAL_SERVICE_UNAVAILABLE"
    return "UNKNOWN"


if settings.static_dir:
    mount_static_site(app, Path(settings.static_dir))

