"""
DocuSpace Phase 9 — Real PostgreSQL Integration Tests: Alembic, FORCE RLS, FKs, Auth & RBAC
"""
import uuid
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.core.database import get_db, reset_tenant_context, set_tenant_context
from backend.app.main import app
from backend.app.models.document import Document, DocumentVersion, Folder
from backend.app.models.plan import Plan
from backend.app.models.tenant import Tenant
from backend.app.models.user import User
from backend.tests.pg_harness import PostgresHarness


@pytest.fixture(scope="module")
def pg_harness():
    harness = PostgresHarness("docuspace_p9_rls")
    harness.start()
    harness.run_alembic_and_grant()
    try:
        yield harness
    finally:
        harness.stop()


@pytest_asyncio.fixture
async def db_session_factory(pg_harness: PostgresHarness):
    engine = create_async_engine(pg_harness.app_async_url, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False)
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
async def test_phase9_pg_alembic_schema_and_seeds(db_session_factory):
    async with db_session_factory() as db:
        tables_res = await db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        tables = {r[0] for r in tables_res.fetchall()}
        for tbl in (
            "plans", "users", "sessions", "tenants", "roles", "tenant_members",
            "storage_usage", "folders", "documents", "document_versions",
            "permissions", "role_permissions", "upload_sessions",
            "shares", "share_recipients", "audit_logs", "notifications",
        ):
            assert tbl in tables

        plans = {p.id: p for p in (await db.execute(select(Plan))).scalars().all()}
        assert plans["FREE"].max_storage_bytes == 524288000
        assert plans["PERSONAL"].max_storage_bytes == 21474836480
        assert plans["PREMIUM"].max_storage_bytes == 107374182400

        roles = {r[0] for r in (await db.execute(text("SELECT name FROM roles"))).fetchall()}
        assert {"OWNER", "EDITOR", "VIEWER", "GUEST"}.issubset(roles)


@pytest.mark.asyncio
async def test_phase9_pg_real_rls_and_cross_tenant_fk_barriers(pg_client: AsyncClient, db_session_factory):
    r1 = await pg_client.post("/api/v1/auth/register", json={
        "email": "rls_alice@example.com", "password": "AliceStrongPassword!2026", "full_name": "Alice RLS",
    })
    r2 = await pg_client.post("/api/v1/auth/register", json={
        "email": "rls_bob@example.com", "password": "BobStrongPassword!2026", "full_name": "Bob RLS",
    })
    assert r1.status_code == 201 and r2.status_code == 201

    login_a = (await pg_client.post("/api/v1/auth/login", json={"email": "rls_alice@example.com", "password": "AliceStrongPassword!2026"})).json()
    login_b = (await pg_client.post("/api/v1/auth/login", json={"email": "rls_bob@example.com", "password": "BobStrongPassword!2026"})).json()
    tenant_a, tenant_b = uuid.UUID(login_a["tenant_id"]), uuid.UUID(login_b["tenant_id"])
    user_a = uuid.UUID(login_a["user_id"])
    hdr_a = {"Authorization": f"Bearer {login_a['access_token']}"}
    hdr_b = {"Authorization": f"Bearer {login_b['access_token']}"}

    fa = await pg_client.post("/api/v1/documents/folders", json={"name": "AliceSecretFolder"}, headers=hdr_a)
    fb = await pg_client.post("/api/v1/documents/folders", json={"name": "BobSecretFolder"}, headers=hdr_b)
    assert fa.status_code == 201 and fb.status_code == 201
    folder_a_id, folder_b_id = uuid.UUID(fa.json()["id"]), uuid.UUID(fb.json()["id"])

    async with db_session_factory() as db:
        assert (await db.execute(select(Folder))).scalars().all() == []

        await set_tenant_context(db, str(tenant_a), is_superuser=False)
        assert {f.id for f in (await db.execute(select(Folder))).scalars().all()} == {folder_a_id}
        assert (await db.execute(select(Folder).where(Folder.id == folder_b_id))).scalar_one_or_none() is None

        db.add(Folder(id=uuid.uuid4(), tenant_id=tenant_b, name="InjectedCrossTenant", created_by=user_a))
        with pytest.raises(ProgrammingError, match="row-level security policy"):
            await db.flush()
        await db.rollback()

        await reset_tenant_context(db)
        assert (await db.execute(select(Folder))).scalars().all() == []

    async with db_session_factory() as db:
        await set_tenant_context(db, str(tenant_a), is_superuser=True)
        doc_id = uuid.uuid4()
        db.add(Document(
            id=doc_id, tenant_id=tenant_a, folder_id=folder_b_id, original_name="cross.pdf",
            storage_key=f"tenants/{tenant_a}/{uuid.uuid4().hex}.pdf", mime_type="application/pdf",
            extension="pdf", size_bytes=123, sha256_hash="0" * 64, status="READY", antivirus_status="CLEAN", created_by=user_a,
        ))
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

        await set_tenant_context(db, str(tenant_a), is_superuser=True)
        db.add(Folder(id=uuid.uuid4(), tenant_id=tenant_a, parent_id=folder_b_id, name="CrossParent", created_by=user_a))
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

        await set_tenant_context(db, str(tenant_a), is_superuser=True)
        db.add(DocumentVersion(
            id=uuid.uuid4(), document_id=uuid.uuid4(), tenant_id=tenant_a, version_number=1,
            storage_key=f"tenants/{tenant_a}/{uuid.uuid4().hex}.pdf", size_bytes=10,
            mime_type="application/pdf", sha256_hash="1" * 64, created_by=user_a,
        ))
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    forged = await pg_client.get("/api/v1/documents/folders", headers={**hdr_a, "X-Tenant-ID": str(tenant_b)})
    assert forged.status_code == 403


@pytest.mark.asyncio
async def test_phase9_pg_auth_sessions_refresh_rotation_and_rbac(pg_client: AsyncClient, db_session_factory):
    await pg_client.post("/api/v1/auth/register", json={"email": "rbac_owner@example.com", "password": "OwnerPassword!2026", "full_name": "Owner RBAC"})
    await pg_client.post("/api/v1/auth/register", json={"email": "rbac_viewer@example.com", "password": "ViewerPassword!2026", "full_name": "Viewer RBAC"})

    async with db_session_factory() as db:
        u = (await db.execute(select(User).where(User.email == "rbac_owner@example.com"))).scalar_one()
        vtok = u.verification_token
    assert (await pg_client.get(f"/api/v1/auth/verify-email?token={vtok}")).status_code == 200

    login_owner = (await pg_client.post("/api/v1/auth/login", json={"email": "rbac_owner@example.com", "password": "OwnerPassword!2026"})).json()
    old_refresh = login_owner["refresh_token"]
    ref_resp = await pg_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert ref_resp.status_code == 200
    assert ref_resp.json()["refresh_token"] != old_refresh
    assert (await pg_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})).status_code == 401

    owner_hdr = {"Authorization": f"Bearer {ref_resp.json()['access_token']}"}
    assert (await pg_client.post("/api/v1/auth/logout", headers=owner_hdr)).status_code == 200

    login_owner = (await pg_client.post("/api/v1/auth/login", json={"email": "rbac_owner@example.com", "password": "OwnerPassword!2026"})).json()
    owner_hdr = {"Authorization": f"Bearer {login_owner['access_token']}"}
    owner_tenant_id = login_owner["tenant_id"]

    async with db_session_factory() as db:
        await set_tenant_context(db, owner_tenant_id, is_superuser=True)
        await db.execute(update(Tenant).where(Tenant.id == uuid.UUID(owner_tenant_id)).values(plan_id="PERSONAL"))
        await db.commit()

    inv = await pg_client.post("/api/v1/tenants/current/members", json={"email": "rbac_viewer@example.com", "role": "VIEWER"}, headers=owner_hdr)
    assert inv.status_code == 201

    login_viewer = (await pg_client.post("/api/v1/auth/login", json={"email": "rbac_viewer@example.com", "password": "ViewerPassword!2026"})).json()
    viewer_hdr = {"Authorization": f"Bearer {login_viewer['access_token']}", "X-Tenant-ID": owner_tenant_id}

    assert (await pg_client.get("/api/v1/documents/folders", headers=viewer_hdr)).status_code == 200
    assert (await pg_client.post("/api/v1/documents/folders", json={"name": "ForbiddenDir"}, headers=viewer_hdr)).status_code == 403
    assert (await pg_client.post("/api/v1/tenants/current/members", json={"email": "x@example.com", "role": "VIEWER"}, headers=viewer_hdr)).status_code == 403

    for _ in range(5):
        await pg_client.post("/api/v1/auth/login", json={"email": "rbac_viewer@example.com", "password": "WrongPassword!"})
    assert (await pg_client.post("/api/v1/auth/login", json={"email": "rbac_viewer@example.com", "password": "ViewerPassword!2026"})).status_code == 429
