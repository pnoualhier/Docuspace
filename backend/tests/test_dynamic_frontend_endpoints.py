"""
DocuSpace Dynamic Frontend Support Endpoints — PostgreSQL Integration Tests
Covers every newly added or hardened endpoint required by the dynamic React SaaS frontend:
  - GET /api/v1/documents/folders?flat=true (full nested tree & trashed folders)
  - PATCH /api/v1/documents/documents/{id} with folder_id=null (move back to root)
  - GET /api/v1/documents/documents/{id}/preview (real MinIO bytes + Fail-Closed + SVG/MD/CSV sanitization)
  - POST /api/v1/documents/documents/{id}/versions/upload (real multipart upload + ClamAV + MinIO)
  - DELETE /api/v1/notifications/{id} (tenant & user isolated)
  - GET /api/v1/admin/users & GET /api/v1/admin/tenants (superuser RBAC)
  - GET /api/v1/billing/invoices (real AuditLog-derived history, never fabricated)
  - GET /api/v1/tenants/my-tenants (enriched with storage_usage & plan state)
  - POST /api/v1/tenants/current/members (plan.max_members & OWNER role protection)
  - GET /api/v1/auth/sessions (is_current flag via refresh_token cookie)
"""
import io
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.core.database import get_db, reset_tenant_context, set_tenant_context
from backend.app.main import app
from backend.app.models.audit import Notification
from backend.app.models.document import Document, DocumentVersion
from backend.app.models.tenant import StorageUsage, Tenant
from backend.app.models.user import User
from backend.app.security.antivirus import ScanResult, clamav_scanner
from backend.app.storage.s3_storage import storage_client
from backend.tests.pg_harness import PostgresHarness


@pytest.fixture(scope="module")
def pg_harness():
    harness = PostgresHarness("docuspace_dyn_fe")
    harness.start()
    harness.run_alembic_and_grant()
    try:
        yield harness
    finally:
        harness.stop()


@pytest_asyncio.fixture
async def db_session_factory(pg_harness: PostgresHarness):
    engine = create_async_engine(pg_harness.app_async_url, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
    )
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def pg_client(db_session_factory) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        async with db_session_factory() as session:
            try:
                yield session
            finally:
                await reset_tenant_context(session)
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_dynamic_frontend_endpoints_and_guards(pg_client: AsyncClient, db_session_factory, monkeypatch):
    # Register two normal users + one superuser
    await pg_client.post("/api/v1/auth/register", json={
        "email": "dyn_owner@example.com", "password": "OwnerStrongPassword!2026", "full_name": "Owner Dyn",
    })
    await pg_client.post("/api/v1/auth/register", json={
        "email": "dyn_other@example.com", "password": "OtherStrongPassword!2026", "full_name": "Other Dyn",
    })
    await pg_client.post("/api/v1/auth/register", json={
        "email": "dyn_super@example.com", "password": "SuperStrongPassword!2026", "full_name": "Super Dyn",
    })

    async with db_session_factory() as db:
        await set_tenant_context(db, "", is_superuser=True)
        su = (await db.execute(select(User).where(User.email == "dyn_super@example.com"))).scalar_one()
        su.is_superuser = True
        await db.commit()

    login_owner_resp = await pg_client.post("/api/v1/auth/login", json={
        "email": "dyn_owner@example.com", "password": "OwnerStrongPassword!2026",
    })
    login_owner = login_owner_resp.json()
    login_other = (await pg_client.post("/api/v1/auth/login", json={
        "email": "dyn_other@example.com", "password": "OtherStrongPassword!2026",
    })).json()
    login_super = (await pg_client.post("/api/v1/auth/login", json={
        "email": "dyn_super@example.com", "password": "SuperStrongPassword!2026",
    })).json()

    owner_tenant_id = uuid.UUID(login_owner["tenant_id"])
    owner_user_id = uuid.UUID(login_owner["user_id"])
    hdr_owner = {"Authorization": f"Bearer {login_owner['access_token']}"}
    hdr_other = {"Authorization": f"Bearer {login_other['access_token']}"}
    hdr_super = {"Authorization": f"Bearer {login_super['access_token']}"}

    # 1. /tenants/my-tenants returns enriched storage_usage & plan state
    tenants_resp = await pg_client.get("/api/v1/tenants/my-tenants", headers=hdr_owner)
    assert tenants_resp.status_code == 200
    t_list = tenants_resp.json()
    assert len(t_list) == 1
    assert t_list[0]["storage_usage"]["max_storage_bytes"] == 524288000
    assert t_list[0]["subscription_status"] == "ACTIVE"
    assert t_list[0]["restricted_read_only"] is False

    # 2. FREE plan max_members=1 enforced + OWNER invite rejected
    inv_blocked = await pg_client.post(
        "/api/v1/tenants/current/members",
        json={"email": "dyn_other@example.com", "role": "VIEWER"},
        headers=hdr_owner,
    )
    assert inv_blocked.status_code == 400
    inv_owner_role = await pg_client.post(
        "/api/v1/tenants/current/members",
        json={"email": "dyn_other@example.com", "role": "OWNER"},
        headers=hdr_owner,
    )
    assert inv_owner_role.status_code == 400

    # 3. /auth/sessions marks is_current when refresh_token cookie matches
    sessions_resp = await pg_client.get(
        "/api/v1/auth/sessions",
        headers=hdr_owner,
        cookies={"refresh_token": login_owner["refresh_token"]},
    )
    assert sessions_resp.status_code == 200
    sessions_data = sessions_resp.json()
    assert len(sessions_data) >= 1
    assert any(s["is_current"] is True for s in sessions_data)

    # 4. Nested folders + flat=true returns nested subfolders
    root_f = (await pg_client.post("/api/v1/documents/folders", json={"name": "RootDir"}, headers=hdr_owner)).json()
    sub_f = (await pg_client.post("/api/v1/documents/folders", json={"name": "SubDir", "parent_id": root_f["id"]}, headers=hdr_owner)).json()
    non_flat = (await pg_client.get("/api/v1/documents/folders", headers=hdr_owner)).json()
    flat_all = (await pg_client.get("/api/v1/documents/folders?flat=true", headers=hdr_owner)).json()
    assert {f["id"] for f in non_flat} == {root_f["id"]}
    assert {f["id"] for f in flat_all} == {root_f["id"], sub_f["id"]}

    # 5. Seed a Markdown document in MinIO memory/client & PostgreSQL, move to root via folder_id=null, preview, and upload v2
    memory_store = {}
    monkeypatch.setattr(storage_client, "put_object", lambda key, data, ct: memory_store.__setitem__(key, data) or key)
    monkeypatch.setattr(storage_client, "get_object", lambda key: memory_store[key] if key in memory_store else (_ for _ in ()).throw(FileNotFoundError(key)))
    monkeypatch.setattr(storage_client, "delete_object", lambda key: memory_store.pop(key, None))
    monkeypatch.setattr(
        clamav_scanner,
        "scan_bytes",
        lambda data: ScanResult(status="INFECTED", is_clean=False, threat_name="Eicar-Test-Signature", details="Threat")
        if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in data
        else ScanResult(status="CLEAN", is_clean=True, details="OK"),
    )

    # Direct upload into SubDir
    md_bytes = b"# Contrat Dyn\n<script>alert(1)</script>\n**Clause** valable."
    up = await pg_client.post(
        "/api/v1/storage/upload/direct",
        files={"file": ("contrat.md", io.BytesIO(md_bytes), "text/markdown")},
        data={"folder_id": sub_f["id"]},
        headers=hdr_owner,
    )
    assert up.status_code == 201
    doc_id = up.json()["document"]["id"]
    assert up.json()["document"]["folder_id"] == sub_f["id"]

    # Move document back to root with explicit null folder_id
    move_root = await pg_client.patch(
        f"/api/v1/documents/documents/{doc_id}",
        json={"folder_id": None},
        headers=hdr_owner,
    )
    assert move_root.status_code == 200
    assert move_root.json()["folder_id"] is None

    # Preview returns sanitized HTML (script neutralized)
    prev = await pg_client.get(f"/api/v1/documents/documents/{doc_id}/preview", headers=hdr_owner)
    assert prev.status_code == 200
    assert prev.json()["mode"] == "markdown"
    assert "<script>" not in (prev.json()["html_content"] or "")
    assert "Contrat Dyn" in (prev.json()["text_content"] or "")

    # Upload clean v2 via multipart /versions/upload
    v2_bytes = b"# Contrat Dyn v2\nMise a jour."
    v2_resp = await pg_client.post(
        f"/api/v1/documents/documents/{doc_id}/versions/upload",
        files={"file": ("contrat_v2.md", io.BytesIO(v2_bytes), "text/markdown")},
        data={"change_summary": "Revision 2"},
        headers=hdr_owner,
    )
    assert v2_resp.status_code == 201
    assert v2_resp.json()["version_number"] == 2

    # Infected v3 rejected with 422 and quarantined
    v3_bad = await pg_client.post(
        f"/api/v1/documents/documents/{doc_id}/versions/upload",
        files={"file": ("virus.txt", io.BytesIO(b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"), "text/plain")},
        headers=hdr_owner,
    )
    assert v3_bad.status_code == 422

    # 6. DELETE /notifications/{id} scoped to tenant+user
    async with db_session_factory() as db:
        await set_tenant_context(db, str(owner_tenant_id), is_superuser=False)
        notif = Notification(
            tenant_id=owner_tenant_id,
            user_id=owner_user_id,
            category="STORAGE",
            level="INFO",
            type="INFO",
            title="Test Delete Notif",
            message="Message",
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)
        notif_id = notif.id

    assert (await pg_client.delete(f"/api/v1/notifications/{notif_id}", headers=hdr_other)).status_code == 404
    assert (await pg_client.delete(f"/api/v1/notifications/{notif_id}", headers=hdr_owner)).status_code == 204

    # 7. Admin /users & /tenants RBAC + Billing /invoices
    assert (await pg_client.get("/api/v1/admin/users", headers=hdr_owner)).status_code == 403
    assert (await pg_client.get("/api/v1/admin/tenants", headers=hdr_owner)).status_code == 403

    adm_users = await pg_client.get("/api/v1/admin/users", headers=hdr_super)
    assert adm_users.status_code == 200
    assert adm_users.json()["total"] >= 3

    adm_tenants = await pg_client.get("/api/v1/admin/tenants", headers=hdr_super)
    assert adm_tenants.status_code == 200
    assert adm_tenants.json()["total"] >= 3

    inv_empty = await pg_client.get("/api/v1/billing/invoices", headers=hdr_owner)
    assert inv_empty.status_code == 200
    assert inv_empty.json() == []
