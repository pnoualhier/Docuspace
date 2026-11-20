"""
DocuSpace Phase 10 — Hardening, Security Audit, PostgreSQL RLS, Redis & Backup/Restore Drill Tests.
Covers every P0/P1/P2 remediation across storage, documents/versions/trash, notifications,
billing webhooks, admin RBAC/CSV sanitization, GDPR portability/erasure, PATCH /shares/{id},
real Redis SlidingRateLimiter, real /api/v1/health probes, and real pg_dump/pg_restore drill.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator
from urllib.parse import urlparse

import pytest
import pytest_asyncio
import redis
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text, update
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.billing.stripe_service import StripeService, stripe_service
from backend.app.core.database import get_db, reset_tenant_context, set_tenant_context
from backend.app.core.rate_limit import SlidingRateLimiter
from backend.app.main import app
from backend.app.models.audit import AuditLog, Notification, QuarantineEvent
from backend.app.models.document import Document, DocumentVersion, Folder
from backend.app.models.share import Share
from backend.app.models.tenant import StorageUsage, Tenant
from backend.app.models.user import Session as UserSession, User
from backend.app.storage.s3_storage import S3Storage, StorageBackendError, storage_client
from backend.app.storage.storage_interface import is_prohibited_extension
from backend.app.storage.upload_service import sanitize_filename
from backend.tests.pg_harness import PostgresHarness, find_free_port


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def pg_harness():
    harness = PostgresHarness("docuspace_p10_audit")
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
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
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


# =========================================================================
# 1. STORAGE FAIL-CLOSED, COPY OBJECT & FILENAME/EXTENSION HARDENING
# =========================================================================

def test_phase10_s3_fail_closed_and_filename_extension_hardening():
    # Unreachable MinIO with use_minio=True must raise StorageBackendError (fail-closed)
    bad_s3 = S3Storage(
        endpoint=f"127.0.0.1:{find_free_port()}",
        access_key="bad_key",
        secret_key="bad_secret",
        bucket_name="docuspace-test",
        secure=False,
        use_minio=True,
    )
    with pytest.raises(StorageBackendError):
        bad_s3.ensure_bucket()
    with pytest.raises(StorageBackendError):
        bad_s3.put_object("tenants/t1/file.txt", b"hello", "text/plain")
    with pytest.raises(StorageBackendError):
        bad_s3.get_object("tenants/t1/file.txt")
    with pytest.raises(StorageBackendError):
        bad_s3.copy_object("tenants/t1/a.txt", "tenants/t1/b.txt")

    # Test-mode copy_object clones payload and raises FileNotFoundError if missing
    local_s3 = S3Storage(use_minio=False)
    local_s3.put_object("tenants/t1/src.pdf", b"%PDF-1.7 test", "application/pdf")
    assert local_s3.copy_object("tenants/t1/src.pdf", "tenants/t1/dst.pdf") is True
    assert local_s3.get_object("tenants/t1/dst.pdf") == b"%PDF-1.7 test"
    with pytest.raises(FileNotFoundError):
        local_s3.copy_object("tenants/t1/missing.pdf", "tenants/t1/dst2.pdf")

    # Path traversal & null-byte filename rejection
    for bad_name in ("../secret.pdf", "dir/../../etc/passwd", "bad\x00name.pdf", "..\\win.txt"):
        with pytest.raises(HTTPException) as exc_info:
            sanitize_filename(bad_name)
        assert exc_info.value.status_code == 400

    assert sanitize_filename("  rapport:2026?.pdf  ") == "rapport_2026_.pdf"

    # Double-extension masquerading check
    assert is_prohibited_extension("facture.exe.pdf") is True
    assert is_prohibited_extension("script.sh.txt") is True
    assert is_prohibited_extension("payload.bat") is True
    assert is_prohibited_extension("rapport.final.pdf") is False


# =========================================================================
# 2. REAL PG RLS FOR NOTIFICATIONS & QUARANTINE + DOCUMENT/VERSION/TRASH LIFECYCLE
# =========================================================================

@pytest.mark.asyncio
async def test_phase10_rls_notifications_quarantine_and_document_lifecycle(
    pg_client: AsyncClient,
    db_session_factory,
):
    reg_a = await pg_client.post("/api/v1/auth/register", json={
        "email": "p10_alice@example.com",
        "password": "AliceStrongPassword!2026",
        "full_name": "Alice P10",
    })
    reg_b = await pg_client.post("/api/v1/auth/register", json={
        "email": "p10_bob@example.com",
        "password": "BobStrongPassword!2026",
        "full_name": "Bob P10",
    })
    assert reg_a.status_code == 201 and reg_b.status_code == 201

    login_a = (await pg_client.post("/api/v1/auth/login", json={
        "email": "p10_alice@example.com",
        "password": "AliceStrongPassword!2026",
    })).json()
    login_b = (await pg_client.post("/api/v1/auth/login", json={
        "email": "p10_bob@example.com",
        "password": "BobStrongPassword!2026",
    })).json()

    tenant_a, user_a = uuid.UUID(login_a["tenant_id"]), uuid.UUID(login_a["user_id"])
    tenant_b, user_b = uuid.UUID(login_b["tenant_id"]), uuid.UUID(login_b["user_id"])
    hdr_a = {"Authorization": f"Bearer {login_a['access_token']}"}
    hdr_b = {"Authorization": f"Bearer {login_b['access_token']}"}

    # Verify FORCE RLS on notifications and quarantine_events in PostgreSQL
    async with db_session_factory() as db:
        await set_tenant_context(db, str(tenant_a), is_superuser=False)
        notif_a = Notification(
            tenant_id=tenant_a,
            user_id=user_a,
            category="STORAGE",
            level="WARNING",
            type="WARNING",
            title="Alerte Alice",
            message="Quota 80%",
        )
        qe_a = QuarantineEvent(
            tenant_id=tenant_a,
            user_id=user_a,
            original_name="bad.pdf",
            threat_name="Eicar-Test-Signature",
            quarantine_key=f"quarantine/{tenant_a}/eicar",
            size_bytes=68,
            status="QUARANTINED",
        )
        db.add(notif_a)
        db.add(qe_a)
        await db.commit()

        # Without tenant context: 0 rows visible
        await reset_tenant_context(db)
        assert (await db.execute(select(Notification))).scalars().all() == []
        assert (await db.execute(select(QuarantineEvent))).scalars().all() == []

        # Tenant B cannot read Alice's notifications/quarantine or insert into tenant_a
        await set_tenant_context(db, str(tenant_b), is_superuser=False)
        assert (await db.execute(select(Notification))).scalars().all() == []
        assert (await db.execute(select(QuarantineEvent))).scalars().all() == []

        db.add(QuarantineEvent(
            tenant_id=tenant_a,
            user_id=user_b,
            original_name="forged.pdf",
            threat_name="Test",
            quarantine_key="quarantine/forged",
            size_bytes=10,
        ))
        with pytest.raises(ProgrammingError, match="row-level security policy"):
            await db.flush()
        await db.rollback()

    # Seed a clean document in storage_client & PostgreSQL for Alice
    doc_id = uuid.uuid4()
    v1_key = f"tenants/{tenant_a}/{doc_id}_v1.pdf"
    storage_client.put_object(v1_key, b"%PDF-1.7 version 1 payload", "application/pdf")

    async with db_session_factory() as db:
        await set_tenant_context(db, str(tenant_a), is_superuser=False)
        db.add(Document(
            id=doc_id,
            tenant_id=tenant_a,
            folder_id=None,
            original_name="Contrat.pdf",
            storage_key=v1_key,
            mime_type="application/pdf",
            extension="pdf",
            size_bytes=1024,
            sha256_hash=hashlib.sha256(b"%PDF-1.7 version 1 payload").hexdigest(),
            status="READY",
            antivirus_status="CLEAN",
            created_by=user_a,
        ))
        db.add(DocumentVersion(
            id=uuid.uuid4(),
            document_id=doc_id,
            tenant_id=tenant_a,
            version_number=1,
            storage_key=v1_key,
            size_bytes=1024,
            mime_type="application/pdf",
            sha256_hash=hashlib.sha256(b"%PDF-1.7 version 1 payload").hexdigest(),
            change_summary="v1",
            created_by=user_a,
        ))
        usage = (await db.execute(select(StorageUsage).where(StorageUsage.tenant_id == tenant_a))).scalar_one()
        usage.used_bytes += 1024
        usage.document_count += 1
        await db.commit()

    # 2a. Copy document -> creates copy in DB + storage_client + updates quota
    copy_resp = await pg_client.post(f"/api/v1/documents/documents/{doc_id}/copy", json={}, headers=hdr_a)
    assert copy_resp.status_code == 200
    copied_doc = copy_resp.json()
    copied_id = uuid.UUID(copied_doc["id"])
    assert copied_doc["original_name"].startswith("Contrat.pdf")

    # 2b. Versioning capped by FREE Plan (max_versions_per_file=3): creating v2, v3, v4 evicts v1 from DB & storage
    for v_num in (2, 3, 4):
        v_resp = await pg_client.post(
            f"/api/v1/documents/documents/{doc_id}/versions",
            json={
                "size_bytes": 2048,
                "mime_type": "application/pdf",
                "sha256_hash": f"{v_num}" * 64,
                "change_summary": f"Revision {v_num}",
            },
            headers=hdr_a,
        )
        assert v_resp.status_code == 201

    vers_resp = await pg_client.get(f"/api/v1/documents/documents/{doc_id}/versions", headers=hdr_a)
    assert vers_resp.status_code == 200
    ver_nums = [v["version_number"] for v in vers_resp.json()]
    assert ver_nums == [4, 3, 2], f"Expected v1 evicted by FREE max_versions_per_file=3, got {ver_nums}"
    assert storage_client.object_exists(v1_key) is False

    # 2c. Recursive folder delete + share deactivation
    parent_f = (await pg_client.post("/api/v1/documents/folders", json={"name": "ParentDir"}, headers=hdr_a)).json()
    child_f = (await pg_client.post(
        "/api/v1/documents/folders",
        json={"name": "ChildDir", "parent_id": parent_f["id"]},
        headers=hdr_a,
    )).json()
    move_copy = await pg_client.patch(
        f"/api/v1/documents/documents/{copied_id}",
        json={"folder_id": child_f["id"]},
        headers=hdr_a,
    )
    assert move_copy.status_code == 200

    shr_resp = await pg_client.post(
        "/api/v1/shares/link",
        json={"document_id": str(copied_id), "role": "VIEWER"},
        headers=hdr_a,
    )
    assert shr_resp.status_code == 201
    share_id = uuid.UUID(shr_resp.json()["id"])

    del_folder = await pg_client.delete(f"/api/v1/documents/folders/{parent_f['id']}", headers=hdr_a)
    assert del_folder.status_code == 204

    async with db_session_factory() as db:
        await set_tenant_context(db, str(tenant_a), is_superuser=False)
        assert (await db.execute(select(Folder.is_trashed).where(Folder.id == uuid.UUID(child_f["id"])))).scalar_one() is True
        assert (await db.execute(select(Document.is_trashed).where(Document.id == copied_id))).scalar_one() is True
        assert (await db.execute(select(Share.is_active).where(Share.id == share_id))).scalar_one() is False

    # 2d. Empty trash reclaims quota & deletes storage objects
    empty_resp = await pg_client.post("/api/v1/documents/trash/empty", headers=hdr_a)
    assert empty_resp.status_code == 200
    assert empty_resp.json()["purged_documents_count"] >= 1
    assert empty_resp.json()["purged_folders_count"] >= 2

    # 2e. Restore & Purge single document
    trash_doc = await pg_client.delete(f"/api/v1/documents/documents/{doc_id}", headers=hdr_a)
    assert trash_doc.status_code == 204
    restore_doc = await pg_client.post(f"/api/v1/documents/documents/{doc_id}/restore", headers=hdr_a)
    assert restore_doc.status_code == 200
    assert restore_doc.json()["is_trashed"] is False

    purge_doc = await pg_client.delete(f"/api/v1/documents/documents/{doc_id}/purge", headers=hdr_a)
    assert purge_doc.status_code == 200
    assert purge_doc.json()["freed_bytes"] > 0

    # Bob cannot read Alice's notifications
    bob_notifs = await pg_client.get("/api/v1/notifications", headers=hdr_b)
    assert bob_notifs.status_code == 200
    assert bob_notifs.json()["total"] == 0


# =========================================================================
# 3. ADMIN RBAC & CSV SANITIZATION, BILLING WEBHOOK, NOTIFICATIONS, PATCH SHARE, GDPR
# =========================================================================

@pytest.mark.asyncio
async def test_phase10_admin_billing_notifications_patch_share_and_gdpr(
    pg_client: AsyncClient,
    db_session_factory,
):
    await pg_client.post("/api/v1/auth/register", json={
        "email": "p10_owner@example.com",
        "password": "OwnerStrongPassword!2026",
        "full_name": "Owner P10",
    })
    await pg_client.post("/api/v1/auth/register", json={
        "email": "p10_editor@example.com",
        "password": "EditorStrongPassword!2026",
        "full_name": "Editor P10",
    })
    await pg_client.post("/api/v1/auth/register", json={
        "email": "p10_super@example.com",
        "password": "SuperStrongPassword!2026",
        "full_name": "Superadmin P10",
    })

    # Promote p10_super to superuser in PostgreSQL
    async with db_session_factory() as db:
        await set_tenant_context(db, "", is_superuser=True)
        su = (await db.execute(select(User).where(User.email == "p10_super@example.com"))).scalar_one()
        su.is_superuser = True
        await db.commit()

    login_owner = (await pg_client.post("/api/v1/auth/login", json={
        "email": "p10_owner@example.com",
        "password": "OwnerStrongPassword!2026",
    })).json()
    login_editor = (await pg_client.post("/api/v1/auth/login", json={
        "email": "p10_editor@example.com",
        "password": "EditorStrongPassword!2026",
    })).json()
    login_super = (await pg_client.post("/api/v1/auth/login", json={
        "email": "p10_super@example.com",
        "password": "SuperStrongPassword!2026",
    })).json()

    owner_tenant_id = uuid.UUID(login_owner["tenant_id"])
    owner_id = uuid.UUID(login_owner["user_id"])
    hdr_owner = {"Authorization": f"Bearer {login_owner['access_token']}"}
    hdr_super = {"Authorization": f"Bearer {login_super['access_token']}"}

    # Temporarily upgrade to PERSONAL to invite collaborator, then restore FREE for 500MB quota tests
    async with db_session_factory() as db:
        await set_tenant_context(db, str(owner_tenant_id), is_superuser=True)
        await db.execute(update(Tenant).where(Tenant.id == owner_tenant_id).values(plan_id="PERSONAL"))
        await db.commit()

    inv = await pg_client.post(
        "/api/v1/tenants/current/members",
        json={"email": "p10_editor@example.com", "role": "EDITOR"},
        headers=hdr_owner,
    )
    assert inv.status_code == 201

    async with db_session_factory() as db:
        await set_tenant_context(db, str(owner_tenant_id), is_superuser=True)
        await db.execute(update(Tenant).where(Tenant.id == owner_tenant_id).values(plan_id="FREE"))
        await db.commit()
    hdr_editor_on_owner = {
        "Authorization": f"Bearer {login_editor['access_token']}",
        "X-Tenant-ID": str(owner_tenant_id),
    }

    # --- 3a. Admin RBAC & CSV Formula Injection Neutralization ---
    assert (await pg_client.get("/api/v1/admin/stats", headers=hdr_owner)).status_code == 403
    assert (await pg_client.get("/api/v1/admin/audit-logs", headers=hdr_owner)).status_code == 403

    stats_resp = await pg_client.get("/api/v1/admin/stats", headers=hdr_super)
    assert stats_resp.status_code == 200
    assert stats_resp.json()["tenants_count"] >= 3

    async with db_session_factory() as db:
        await set_tenant_context(db, str(owner_tenant_id), is_superuser=True)
        db.add(AuditLog(
            tenant_id=owner_tenant_id,
            user_id=owner_id,
            action="=CMD('calc')",
            resource_type="DOCUMENT",
            ip_address="+1.2.3.4",
        ))
        await db.commit()

    csv_resp = await pg_client.get("/api/v1/admin/audit-logs?format=csv", headers=hdr_super)
    assert csv_resp.status_code == 200
    assert "'=CMD('calc')" in csv_resp.text
    assert "'+1.2.3.4" in csv_resp.text

    # --- 3b. Notifications check-quota (80% & 100%) + read ---
    async with db_session_factory() as db:
        await set_tenant_context(db, str(owner_tenant_id), is_superuser=False)
        usage = (await db.execute(select(StorageUsage).where(StorageUsage.tenant_id == owner_tenant_id))).scalar_one()
        usage.used_bytes = int(524288000 * 0.85)  # 85% of 500 Mo FREE plan
        await db.commit()

    q_warn = await pg_client.post("/api/v1/notifications/check-quota", headers=hdr_owner)
    assert q_warn.status_code == 200
    assert q_warn.json()["alert_created"] is True
    assert q_warn.json()["notification"]["level"] == "WARNING"
    notif_id = q_warn.json()["notification"]["id"]

    mark_one = await pg_client.post(f"/api/v1/notifications/{notif_id}/read", headers=hdr_owner)
    assert mark_one.status_code == 200
    assert mark_one.json()["success"] is True

    # --- 3c. Billing Checkout + HMAC Webhook + Downgrade Read-Only Lock ---
    assert StripeService(webhook_secret="").verify_webhook_signature(b"{}", "t=1,v1=abc") is False

    chk_resp = await pg_client.post(
        "/api/v1/billing/checkout",
        json={"plan_id": "PERSONAL", "billing_interval": "monthly"},
        headers=hdr_owner,
    )
    assert chk_resp.status_code == 200
    assert chk_resp.json()["tenant_id"] == str(owner_tenant_id)

    # Forged signature rejected (400)
    bad_wh = await pg_client.post(
        "/api/v1/billing/webhook",
        content=b'{"type":"checkout.session.completed","data":{"object":{"tenant_id":"' + str(owner_tenant_id).encode() + b'","plan_id":"PERSONAL"}}}',
        headers={"Stripe-Signature": "t=9999999999,v1=deadbeef"},
    )
    assert bad_wh.status_code == 400

    # Valid upgrade webhook -> PERSONAL
    up_payload = json.dumps({
        "type": "checkout.session.completed",
        "data": {"object": {"tenant_id": str(owner_tenant_id), "plan_id": "PERSONAL"}},
    }).encode("utf-8")
    up_sig = stripe_service.generate_webhook_signature(up_payload)
    up_wh = await pg_client.post(
        "/api/v1/billing/webhook",
        content=up_payload,
        headers={"Stripe-Signature": up_sig},
    )
    assert up_wh.status_code == 200
    assert up_wh.json()["status"] == "ACTIVE"

    # Simulate 2 Go usage > 500 Mo FREE quota, then cancel -> restricted_read_only=True
    async with db_session_factory() as db:
        await set_tenant_context(db, str(owner_tenant_id), is_superuser=False)
        usage = (await db.execute(select(StorageUsage).where(StorageUsage.tenant_id == owner_tenant_id))).scalar_one()
        usage.used_bytes = 2 * 1024 * 1024 * 1024
        await db.commit()

    down_payload = json.dumps({
        "type": "customer.subscription.deleted",
        "data": {"object": {"tenant_id": str(owner_tenant_id)}},
    }).encode("utf-8")
    down_sig = stripe_service.generate_webhook_signature(down_payload)
    down_wh = await pg_client.post(
        "/api/v1/billing/webhook",
        content=down_payload,
        headers={"Stripe-Signature": down_sig},
    )
    assert down_wh.status_code == 200

    async with db_session_factory() as db:
        await set_tenant_context(db, str(owner_tenant_id), is_superuser=False)
        t_row = (await db.execute(select(Tenant).where(Tenant.id == owner_tenant_id))).scalar_one()
        assert t_row.plan_id == "FREE"
        assert t_row.subscription_status == "CANCELED"
        assert t_row.restricted_read_only is True

    # --- 3d. PATCH /api/v1/shares/{share_id} ---
    doc_id = uuid.uuid4()
    doc_key = f"tenants/{owner_tenant_id}/{doc_id}.pdf"
    storage_client.put_object(doc_key, b"%PDF-1.7 share doc", "application/pdf")
    async with db_session_factory() as db:
        await set_tenant_context(db, str(owner_tenant_id), is_superuser=False)
        db.add(Document(
            id=doc_id,
            tenant_id=owner_tenant_id,
            original_name="Partage.pdf",
            storage_key=doc_key,
            mime_type="application/pdf",
            extension="pdf",
            size_bytes=512,
            sha256_hash="a" * 64,
            status="READY",
            antivirus_status="CLEAN",
            created_by=owner_id,
        ))
        await db.commit()

    created_share = await pg_client.post(
        "/api/v1/shares/link",
        json={"document_id": str(doc_id), "role": "VIEWER", "max_downloads": 5},
        headers=hdr_owner,
    )
    assert created_share.status_code == 201
    share_id = created_share.json()["id"]

    # Non-creator EDITOR cannot modify owner's share (403)
    forbidden_patch = await pg_client.patch(
        f"/api/v1/shares/{share_id}",
        json={"max_downloads": 99},
        headers=hdr_editor_on_owner,
    )
    assert forbidden_patch.status_code == 403

    # Owner updates role, password, max_downloads, is_active
    ok_patch = await pg_client.patch(
        f"/api/v1/shares/{share_id}",
        json={"role": "EDITOR", "password": "NewLinkPassword!2026", "max_downloads": 2, "is_active": False},
        headers=hdr_owner,
    )
    assert ok_patch.status_code == 200
    body = ok_patch.json()
    assert body["role"] == "EDITOR"
    assert body["has_password"] is True
    assert body["max_downloads"] == 2
    assert body["is_active"] is False

    # --- 3e. GDPR Export (Art. 20) & Account Erasure (Art. 17) ---
    gdpr_exp = await pg_client.get("/api/v1/gdpr/export", headers=hdr_owner)
    assert gdpr_exp.status_code == 200
    exp_json = gdpr_exp.json()
    assert exp_json["user_profile"]["email"] == "p10_owner@example.com"
    assert len(exp_json["documents"]) >= 1

    # IDOR & wrong phrase blocked
    assert (await pg_client.post(
        "/api/v1/gdpr/delete-account",
        json={"user_id": str(uuid.uuid4()), "confirmation_phrase": "SUPPRIMER"},
        headers=hdr_owner,
    )).status_code == 403
    assert (await pg_client.post(
        "/api/v1/gdpr/delete-account",
        json={"confirmation_phrase": "NON"},
        headers=hdr_owner,
    )).status_code == 400

    # Actual erasure purges PG rows and deletes S3 storage object
    del_acc = await pg_client.post(
        "/api/v1/gdpr/delete-account",
        json={"confirmation_phrase": "SUPPRIMER"},
        headers=hdr_owner,
    )
    assert del_acc.status_code == 200
    assert del_acc.json()["status"] == "PURGED_COMPLETELY"
    assert storage_client.object_exists(doc_key) is False

    async with db_session_factory() as db:
        await set_tenant_context(db, "", is_superuser=True)
        assert (await db.execute(select(User).where(User.id == owner_id))).scalar_one_or_none() is None
        assert (await db.execute(select(Tenant).where(Tenant.id == owner_tenant_id))).scalar_one_or_none() is None
        assert (await db.execute(select(UserSession).where(UserSession.user_id == owner_id))).scalars().all() == []


# =========================================================================
# 4. REAL REDIS SLIDING RATE LIMITER & REAL /api/v1/health PROBES
# =========================================================================

@pytest.mark.asyncio
async def test_phase10_real_redis_rate_limiter_and_health_endpoint(pg_client: AsyncClient):
    ci_redis_url = os.getenv("REDIS_URL", "").strip()
    proc = None
    tmpdir = None

    if ci_redis_url and os.getenv("GITHUB_ACTIONS") == "true":
        redis_url = ci_redis_url
    else:
        redis_bin = shutil.which("redis-server")
        if not redis_bin:
            pytest.skip("redis-server non installé")
        port = find_free_port()
        password = "p10_redis_secret_password"
        tmpdir = tempfile.mkdtemp(prefix="docuspace_p10_redis_")
        proc = subprocess.Popen(
            [
                redis_bin,
                "--port", str(port),
                "--bind", "127.0.0.1",
                "--requirepass", password,
                "--dir", tmpdir,
                "--save", "",
                "--appendonly", "no",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        redis_url = f"redis://:{password}@127.0.0.1:{port}/0"
        client = redis.from_url(redis_url, decode_responses=True)
        for _ in range(30):
            try:
                if client.ping():
                    break
            except Exception:
                time.sleep(0.1)

    try:
        limiter_a = SlidingRateLimiter(namespace="p10test", max_attempts=3, window_seconds=60, redis_url=redis_url)
        limiter_b = SlidingRateLimiter(namespace="p10test", max_attempts=3, window_seconds=60, redis_url=redis_url)
        ident = f"user-{uuid.uuid4().hex}"

        assert limiter_a.is_rate_limited(ident) is False
        assert limiter_a.record_failed_attempt(ident) == 1
        assert limiter_b.record_failed_attempt(ident) == 2
        assert limiter_a.record_failed_attempt(ident) == 3
        # Shared distributed state across separate limiter instances
        assert limiter_b.is_rate_limited(ident) is True

        raw_client = redis.from_url(redis_url, decode_responses=True)
        ttl = raw_client.ttl(f"docuspace:ratelimit:p10test:{ident}")
        assert 0 < ttl <= 60

        limiter_a.reset_attempts(ident)
        assert limiter_b.is_rate_limited(ident) is False
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # Real /api/v1/health endpoint check against real PG
    health_resp = await pg_client.get("/api/v1/health")
    assert health_resp.status_code == 200
    h = health_resp.json()
    assert h["database"] == "healthy"
    assert h["status"] in ("healthy", "degraded")
    assert "redis" in h and "storage" in h and "antivirus" in h


# =========================================================================
# 5. REAL PG_DUMP / SHA256SUM / PG_RESTORE DRILL & BACKUP SCRIPT SYNTAX
# =========================================================================

def test_phase10_real_pg_dump_checksum_and_pg_restore_drill(pg_harness: PostgresHarness):
    # Verify backup & restore shell script syntax
    for script in ("scripts/backup/backup.sh", "scripts/restore/restore.sh"):
        subprocess.run(["bash", "-n", str(REPO_ROOT / script)], check=True)

    pg_dump_bin = str(pg_harness.pg_bin / "pg_dump") if (pg_harness.pg_bin / "pg_dump").exists() else shutil.which("pg_dump")
    pg_restore_bin = str(pg_harness.pg_bin / "pg_restore") if (pg_harness.pg_bin / "pg_restore").exists() else shutil.which("pg_restore")
    psql_bin = str(pg_harness.pg_bin / "psql") if (pg_harness.pg_bin / "psql").exists() else shutil.which("psql")
    if not (pg_dump_bin and pg_restore_bin and psql_bin):
        pytest.skip("pg_dump/pg_restore/psql non disponibles")

    parsed = urlparse(pg_harness.super_sync_url)
    host = parsed.hostname or "127.0.0.1"
    port = str(parsed.port or 5432)
    user = parsed.username or "pgadmin"
    password = parsed.password or ""
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    restored_db = f"docuspace_p10_restored_{uuid.uuid4().hex[:6]}"
    tmpdir = tempfile.mkdtemp(prefix="docuspace_p10_backup_")
    try:
        dump_file = Path(tmpdir) / "postgres_docuspace_drill.dump"
        checksum_file = Path(tmpdir) / "SHA256SUMS"

        subprocess.run(
            [pg_dump_bin, "-h", host, "-p", port, "-U", user, "-d", pg_harness.db_name, "-F", "c", "-b", "-f", str(dump_file)],
            env=env,
            check=True,
        )
        assert dump_file.exists() and dump_file.stat().st_size > 0

        digest = hashlib.sha256(dump_file.read_bytes()).hexdigest()
        checksum_file.write_text(f"{digest}  {dump_file.name}\n", encoding="utf-8")
        subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=tmpdir, check=True, stdout=subprocess.DEVNULL)

        subprocess.run(
            [psql_bin, "-h", host, "-p", port, "-U", user, "-d", "postgres", "-c", f"CREATE DATABASE {restored_db};"],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        ext_sql = (REPO_ROOT / "scripts/init/01_extensions.sql").read_text(encoding="utf-8")
        subprocess.run(
            [psql_bin, "-h", host, "-p", port, "-U", user, "-d", restored_db, "-c", ext_sql],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [pg_restore_bin, "-h", host, "-p", port, "-U", user, "-d", restored_db, "--no-owner", str(dump_file)],
            env=env,
            check=True,
        )

        # Verify restored plans count and FORCE RLS flags on critical tables
        verify_sql = (
            "SELECT count(*) FROM plans; "
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname IN ('documents','folders','shares','notifications','quarantine_events') "
            "AND c.relrowsecurity = true AND c.relforcerowsecurity = true;"
        )
        res = subprocess.run(
            [psql_bin, "-h", host, "-p", port, "-U", user, "-d", restored_db, "-t", "-A", "-c", verify_sql],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        assert int(lines[0]) >= 3
        assert int(lines[1]) == 5
    finally:
        subprocess.run(
            [psql_bin, "-h", host, "-p", port, "-U", user, "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {restored_db};"],
            env=env,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        shutil.rmtree(tmpdir, ignore_errors=True)
