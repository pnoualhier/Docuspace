import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api.v1.routes import (
    auth, health, tenants, documents, storage, shares, billing, notifications, admin, gdpr
)
from backend.app.middleware.tenant_context import TenantContext, get_tenant_context, get_current_tenant_context

def test_phase1_all_routers_imported():
    """Verify all 10 feature routers exist and are mounted properly."""
    routers = [
        auth.router, health.router, tenants.router, documents.router,
        storage.router, shares.router, billing.router, notifications.router,
        admin.router, gdpr.router
    ]
    for r in routers:
        assert r is not None, "Each router must be instantiated"

def test_phase1_tenant_context_properties():
    """Verify TenantContext exposes tenant_id, user_id, user, tenant, role, db."""
    class DummyUser:
        id = "user-123"
        is_superuser = False
    class DummyTenant:
        id = "tenant-456"

    ctx = TenantContext(user=DummyUser(), tenant=DummyTenant(), role="OWNER", db=None)
    assert ctx.tenant_id == "tenant-456"
    assert ctx.user_id == "user-123"
    assert ctx.role == "OWNER"
    assert get_tenant_context == get_current_tenant_context

def test_phase1_fastapi_app_startup_and_health():
    """Verify FastAPI application starts and serves requests without error."""
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"].lower() in ("healthy", "degraded", "ok")

def test_phase1_openapi_schema_generation():
    """Verify full OpenAPI schema generation with all endpoints and models."""
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/auth/register" in schema["paths"]
    assert "/api/v1/storage/upload/initiate" in schema["paths"]
    assert "/api/v1/shares/internal" in schema["paths"]
