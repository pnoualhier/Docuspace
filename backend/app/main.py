from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings, is_test_runtime
from backend.app.api.v1.routes import (
    auth,
    health,
    tenants,
    documents,
    storage,
    shares,
    billing,
    notifications,
    admin,
    gdpr,
)


class _StructuredJsonFormatter(logging.Formatter):
    """Structured JSON log formatter excluding sensitive credentials/headers."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for attr in ("request_id", "method", "path", "status_code", "duration_ms"):
            val = getattr(record, attr, None)
            if val is not None:
                payload[attr] = val
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> logging.Logger:
    logger = logging.getLogger("docuspace.api")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_StructuredJsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


api_logger = _configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.APP_ENV == "production" and not is_test_runtime():
        settings.validate_production_secrets()
    api_logger.info("DocuSpace API started (env=%s)", settings.APP_ENV)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="DocuSpace — API REST modulaire et sécurisée pour la gestion documentaire multi-tenant personnelle.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID, Structured Logging & Security Headers middleware
@app.middleware("http")
async def add_process_time_and_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    duration_ms = round(process_time * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"

    api_logger.info(
        "http_request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


# Global Exception Handler (never leaks stacktraces to HTTP clients)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    api_logger.error(
        "unhandled_exception: %s",
        type(exc).__name__,
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": 500,
        },
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Une erreur interne inattendue s'est produite.",
            "request_id": request_id,
        },
    )


# Include API v1 Routers
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth")
app.include_router(tenants.router, prefix=f"{settings.API_V1_STR}/tenants")
app.include_router(documents.router, prefix=f"{settings.API_V1_STR}/documents")
app.include_router(storage.router, prefix=f"{settings.API_V1_STR}/storage")
app.include_router(shares.router, prefix=f"{settings.API_V1_STR}/shares")
app.include_router(billing.router, prefix=settings.API_V1_STR)
app.include_router(notifications.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(gdpr.router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Racine"])
async def root():
    return {
        "service": "DocuSpace Backend API",
        "status": "online",
        "documentation": "/docs",
        "version": "1.0.0",
    }
