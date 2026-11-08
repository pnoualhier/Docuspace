import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.core.config import settings
from backend.app.api.v1.routes import auth, health, tenants, documents

app = FastAPI(
    title=settings.APP_NAME,
    description="DocuSpace — API REST modulaire et sécurisée pour la gestion documentaire multi-tenant personnelle.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID & Observability middleware
@app.middleware("http")
async def add_process_time_and_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    # Strict Security Headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Une erreur interne inattendue s'est produite.",
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )

# Include API v1 Routers
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth")
app.include_router(tenants.router, prefix=f"{settings.API_V1_STR}/tenants")
app.include_router(documents.router, prefix=f"{settings.API_V1_STR}/documents")

@app.get("/", tags=["Racine"])
async def root():
    return {
        "service": "DocuSpace Backend API",
        "status": "online",
        "documentation": "/docs",
        "version": "1.0.0"
    }
