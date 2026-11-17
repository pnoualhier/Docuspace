"""
DocuSpace Phase 9 — Real PostgreSQL 15+ Integration Tests
Executes against an authentic PostgreSQL server (no SQLite/mock DB):
  - Full Alembic upgrade head (0001 -> 0007)
  - Unprivileged PostgreSQL role (NOSUPERUSER NOBYPASSRLS) with FORCE ROW LEVEL SECURITY
  - Multi-tenant RLS isolation, cross-tenant composite FK integrity, pool context reset
  - Auth lifecycle (register, email verification, Argon2id login, persisted Session, refresh rotation, logout, lockout)
  - RBAC permissions matrix (OWNER vs EDITOR vs VIEWER)
  - Concurrent quota reservations under PostgreSQL SELECT ... FOR UPDATE row locking
  - End-to-end file import + real TCP ClamAV INSTREAM (CLEAN / EICAR INFECTED / Fail-Closed offline)
  - Share persistence in PostgreSQL + concurrent max_downloads locking + audit_logs
  - Real pg_dump + pg_restore round-trip verification
"""
import asyncio
import hashlib
import os
import shutil
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.core.database import (
    get_db,
    reset_tenant_context,
    set_public_share_context,
    set_tenant_context,
)
from backend.app.main import app
from backend.app.models.audit import AuditLog
from backend.app.models.document import Document, Folder
from backend.app.models.plan import Plan
from backend.app.models.share import Share
from backend.app.models.tenant import StorageUsage
from backend.app.models.user import User
from backend.app.security.antivirus import EICAR_SIGNATURE, clamav_scanner
from backend.app.security.password import hash_share_token
from backend.app.services.quota_service import QuotaExceededError, quota_service

REPO_ROOT = Path(__file__).resolve().parents[2]
PG_BIN = Path("/usr/lib/postgresql/15/bin")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _RealTCPClamAVServer:
    """Real TCP server implementing the ClamAV zINSTREAM protocol for E2E scanner tests."""

    def __init__(self, fail_mode: str | None = None):
        self.host = "127.0.0.1"
        self.port = _find_free_port()
        self.fail_mode = fail_mode
        self._server = None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            header = await reader.readuntil(b"\x00")
            if header == b"zINSTREAM\x00":
                chunks = []
                while True:
                    size_bytes = await reader.readexactly(4)
                    chunk_len = int.from_bytes(size_bytes, "big")
                    if chunk_len == 0:
                        break
                    chunks.append(await reader.readexactly(chunk_len))
                payload = b"".join(chunks)

                if self.fail_mode == "corrupt":
                    writer.write(b"GARBAGE_UNPARSABLE_RESPONSE\x00")
                elif EICAR_SIGNATURE in payload:
                    writer.write(b"stream: Eicar-Test-Signature FOUND\x00")
                else:
                    writer.write(b"stream: OK\x00")
                await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()

    async def start(self):
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()


class _PostgresHarness:
    def __init__(self):
        self.external_url = os.getenv("TEST_DATABASE_URL", "").strip()
        self.tmpdir = None
        self.port = 5432
        self.pg_bin = PG_BIN
        self.super_sync_url = ""
        self.app_async_url = ""
        self.super_async_url = ""
        self.db_name = "docuspace_test"

    def start(self):
        if self.external_url:
            self.super_async_url = self.external_url
            self.super_sync_url = self.external_url.replace("+asyncpg", "")
            self.app_async_url = os.getenv("TEST_APP_DATABASE_URL", self.external_url)
            self._ensure_extensions_and_app_role()
            return

        if not (self.pg_bin / "initdb").exists():
            pytest.skip("PostgreSQL binaire introuvable et TEST_DATABASE_URL non défini")

        self.port = _find_free_port()
        self.tmpdir = tempfile.mkdtemp(prefix="docuspace_pg_p9_")
        os.chmod(self.tmpdir, 0o777)
        data_dir = Path(self.tmpdir) / "data"
        log_file = Path(self.tmpdir) / "pg.log"
        data_dir.mkdir()
        subprocess.run(["chown", "-R", "nobody:nogroup", self.tmpdir], check=True)

        init_cmd = (
            f"{self.pg_bin}/initdb -D {data_dir} -U pgadmin --auth=trust -E UTF8 >/dev/null && "
            f"{self.pg_bin}/pg_ctl -D {data_dir} -o '-k {self.tmpdir} -p {self.port} -h 127.0.0.1' "
            f"-l {log_file} start"
        )
        subprocess.run(["su", "-s", "/bin/sh", "nobody", "-c", init_cmd], check=True)

        self.super_sync_url = f"postgresql://pgadmin@127.0.0.1:{self.port}/{self.db_name}"
        self.super_async_url = f"postgresql+asyncpg://pgadmin@127.0.0.1:{self.port}/{self.db_name}"
        self.app_async_url = f"postgresql+asyncpg://docuspace_app:AppTestPass99!@127.0.0.1:{self.port}/{self.db_name}"

        subprocess.run(
            [str(self.pg_bin / "psql"), "-h", "127.0.0.1", "-p", str(self.port), "-U", "pgadmin", "-d", "postgres", "-c", f"CREATE DATABASE {self.db_name};"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        self._ensure_extensions_and_app_role()

    def _run_psql(self, sql: str, db: str | None = None):
        target_db = db or self.db_name
        if self.external_url:
            env = os.environ.copy()
            subprocess.run(["psql", self.super_sync_url, "-c", sql], check=True, env=env, stdout=subprocess.DEVNULL)
        else:
            subprocess.run(
                [str(self.pg_bin / "psql"), "-h", "127.0.0.1", "-p", str(self.port), "-U", "pgadmin", "-d", target_db, "-c", sql],
                check=True,
                stdout=subprocess.DEVNULL,
            )

    def _ensure_extensions_and_app_role(self):
        ext_sql = (REPO_ROOT / "scripts/init/01_extensions.sql").read_text(encoding="utf-8")
        self._run_psql(ext_sql)
        self._run_psql(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'docuspace_app') THEN "
            "CREATE ROLE docuspace_app LOGIN PASSWORD 'AppTestPass99!' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; "
            "END IF; END $$;"
        )

    def run_alembic_and_grant(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["DATABASE_URL"] = self.super_async_url
        subprocess.run(
            ["alembic", "-c", str(REPO_ROOT / "backend/alembic.ini"), "upgrade", "head"],
            cwd=str(REPO_ROOT),
            env=env,
            check=True,
        )
        self._run_psql(
            "GRANT USAGE ON SCHEMA public TO docuspace_app; "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO docuspace_app; "
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO docuspace_app;"
        )

    def stop(self):
        if self.tmpdir and Path(self.tmpdir).exists():
            data_dir = Path(self.tmpdir) / "data"
            subprocess.run(
                ["su", "-s", "/bin/sh", "nobody", "-c", f"{self.pg_bin}/pg_ctl -D {data_dir} stop -m immediate >/dev/null 2>&1 || true"],
                check=False,
            )
            shutil.rmtree(self.tmpdir, ignore_errors=True)


@pytest.fixture(scope="module")
def pg_harness():
    harness = _PostgresHarness()
    harness.start()
    harness.run_alembic_and_grant()
    try:
        yield harness
    finally:
        harness.stop()


@pytest_asyncio.fixture
async def db_session_factory(pg_harness: _PostgresHarness):
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
async def test_phase9_pg_alembic_schema_plans_and_roles_seeded(db_session_factory):
    async with db_session_factory() as db:
        tables_res = await db.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = {r[0] for r in tables_res.fetchall()}
        expected_tables = {
            "plans", "users", "sessions", "tenants", "roles", "tenant_members",
            "storage_usage", "folders", "documents", "document_versions",
            "permissions", "role_permissions", "upload_sessions",
            "shares", "share_recipients", "audit_logs", "notifications",
        }
        assert expected_tables.issubset(tables)

        plans_res = await db.execute(select(Plan))
        plans = {p.id: p for p in plans_res.scalars().all()}
        assert plans["FREE"].max_storage_bytes == 524288000
        assert plans["PERSONAL"].max_storage_bytes == 21474836480
        assert plans["PREMIUM"].max_storage_bytes == 107374182400

        roles_res = await db.execute(text("SELECT name FROM roles"))
        assert {"OWNER", "EDITOR", "VIEWER", "GUEST"}.issubset({r[0] for r in roles_res.fetchall()})


@pytest.mark.asyncio
async def test_phase9_pg_real_rls_and_cross_tenant_fk_isolation(pg_client: AsyncClient, db_session_factory):
    r1 = await pg_client.post("/api/v1/auth/register", json={
        "email": "rls_alice@example.com",
        "password": "AliceStrongPassword!2026",
        "full_name": "Alice RLS",
    })
    r2 = await pg_client.post("/api/v1/auth/register", json={
        "email": "rls_bob@example.com",
        "password": "BobStrongPassword!2026",
        "full_name": "Bob RLS",
    })
    assert r1.status_code == 201 and r2.status_code == 201

    login_a = (await pg_client.post("/api/v1/auth/login", json={"email": "rls_alice@example.com", "password": "AliceStrongPassword!2026"})).json()
    login_b = (await pg_client.post("/api/v1/auth/login", json={"email": "rls_bob@example.com", "password": "BobStrongPassword!2026"})).json()
    tenant_a = uuid.UUID(login_a["tenant_id"])
    tenant_b = uuid.UUID(login_b["tenant_id"])
    user_a = uuid.UUID(login_a["user_id"])

    hdr_a = {"Authorization": f"Bearer {login_a['access_token']}"}
    hdr_b = {"Authorization": f"Bearer {login_b['access_token']}"}

    fa_resp = await pg_client.post("/api/v1/documents/folders", json={"name": "AliceSecretFolder"}, headers=hdr_a)
    fb_resp = await pg_client.post("/api/v1/documents/folders", json={"name": "BobSecretFolder"}, headers=hdr_b)
    assert fa_resp.status_code == 201 and fb_resp.status_code == 201
    folder_a_id = uuid.UUID(fa_resp.json()["id"])
    folder_b_id = uuid.UUID(fb_resp.json()["id"])

    async with db_session_factory() as db:
        no_ctx_rows = (await db.execute(select(Folder))).scalars().all()
        assert len(no_ctx_rows) == 0, "RLS doit masquer toutes les lignes sans app.current_tenant_id"

        await set_tenant_context(db, str(tenant_a), is_superuser=False)
        alice_rows = (await db.execute(select(Folder))).scalars().all()
        assert {f.id for f in alice_rows} == {folder_a_id}
        bob_lookup = (await db.execute(select(Folder).where(Folder.id == folder_b_id))).scalar_one_or_none()
        assert bob_lookup is None

        db.add(Folder(
            id=uuid.uuid4(),
            tenant_id=tenant_b,
            name="InjectedCrossTenant",
            created_by=user_a,
        ))
        with pytest.raises(ProgrammingError, match="row-level security policy"):
            await db.flush()
        await db.rollback()

        await reset_tenant_context(db)
        assert (await db.execute(select(Folder))).scalars().all() == []

    async with db_session_factory() as db:
        await set_tenant_context(db, str(tenant_a), is_superuser=True)
        db.add(Document(
            id=uuid.uuid4(),
            tenant_id=tenant_a,
            folder_id=folder_b_id,
            original_name="cross_tenant.pdf",
            storage_key=f"tenants/{tenant_a}/{uuid.uuid4().hex}.pdf",
            mime_type="application/pdf",
            extension="pdf",
            size_bytes=123,
            sha256_hash="0" * 64,
            status="READY",
            antivirus_status="CLEAN",
            created_by=user_a,
        ))
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

        await set_tenant_context(db, str(tenant_a), is_superuser=True)
        db.add(Folder(
            id=uuid.uuid4(),
            tenant_id=tenant_a,
            parent_id=folder_b_id,
            name="CrossParent",
            created_by=user_a,
        ))
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    forged = await pg_client.get("/api/v1/documents/folders", headers={**hdr_a, "X-Tenant-ID": str(tenant_b)})
    assert forged.status_code == 403


@pytest.mark.asyncio
async def test_phase9_pg_auth_sessions_refresh_rotation_and_rbac(pg_client: AsyncClient, db_session_factory):
    await pg_client.post("/api/v1/auth/register", json={
        "email": "rbac_owner@example.com",
        "password": "OwnerPassword!2026",
        "full_name": "Owner RBAC",
    })
    await pg_client.post("/api/v1/auth/register", json={
        "email": "rbac_viewer@example.com",
        "password": "ViewerPassword!2026",
        "full_name": "Viewer RBAC",
    })

    async with db_session_factory() as db:
        u = (await db.execute(select(User).where(User.email == "rbac_owner@example.com"))).scalar_one()
        vtok = u.verification_token
    vresp = await pg_client.get(f"/api/v1/auth/verify-email?token={vtok}")
    assert vresp.status_code == 200

    login_owner = (await pg_client.post("/api/v1/auth/login", json={
        "email": "rbac_owner@example.com",
        "password": "OwnerPassword!2026",
    })).json()
    old_refresh = login_owner["refresh_token"]
    ref_resp = await pg_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert ref_resp.status_code == 200
    new_refresh = ref_resp.json()["refresh_token"]
    assert new_refresh != old_refresh

    replay_resp = await pg_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay_resp.status_code == 401

    owner_hdr = {"Authorization": f"Bearer {ref_resp.json()['access_token']}"}
    logout_resp = await pg_client.post("/api/v1/auth/logout", headers=owner_hdr)
    assert logout_resp.status_code == 200

    login_owner = (await pg_client.post("/api/v1/auth/login", json={
        "email": "rbac_owner@example.com",
        "password": "OwnerPassword!2026",
    })).json()
    owner_hdr = {"Authorization": f"Bearer {login_owner['access_token']}"}
    owner_tenant_id = login_owner["tenant_id"]

    inv = await pg_client.post(
        "/api/v1/tenants/current/members",
        json={"email": "rbac_viewer@example.com", "role": "VIEWER"},
        headers=owner_hdr,
    )
    assert inv.status_code == 201

    login_viewer = (await pg_client.post("/api/v1/auth/login", json={
        "email": "rbac_viewer@example.com",
        "password": "ViewerPassword!2026",
    })).json()
    viewer_hdr = {
        "Authorization": f"Bearer {login_viewer['access_token']}",
        "X-Tenant-ID": owner_tenant_id,
    }

    assert (await pg_client.get("/api/v1/documents/folders", headers=viewer_hdr)).status_code == 200
    assert (await pg_client.post("/api/v1/documents/folders", json={"name": "ForbiddenDir"}, headers=viewer_hdr)).status_code == 403
    assert (await pg_client.post("/api/v1/tenants/current/members", json={"email": "x@example.com", "role": "VIEWER"}, headers=viewer_hdr)).status_code == 403

    for _ in range(5):
        await pg_client.post("/api/v1/auth/login", json={"email": "rbac_viewer@example.com", "password": "WrongPassword!"})
    locked = await pg_client.post("/api/v1/auth/login", json={"email": "rbac_viewer@example.com", "password": "ViewerPassword!2026"})
    assert locked.status_code == 429


@pytest.mark.asyncio
async def test_phase9_pg_concurrent_quotas_for_update_locking(pg_client: AsyncClient, db_session_factory):
    await pg_client.post("/api/v1/auth/register", json={
        "email": "quota_race@example.com",
        "password": "QuotaRacePassword!2026",
        "full_name": "Quota Race",
    })
    login = (await pg_client.post("/api/v1/auth/login", json={
        "email": "quota_race@example.com",
        "password": "QuotaRacePassword!2026",
    })).json()
    tenant_id = uuid.UUID(login["tenant_id"])

    max_free = 524_288_000
    used_init = max_free - 45_000_000
    async with db_session_factory() as db:
        await set_tenant_context(db, str(tenant_id))
        usage = (await db.execute(select(StorageUsage).where(StorageUsage.tenant_id == tenant_id))).scalar_one()
        usage.used_bytes = used_init
        usage.reserved_bytes = 0
        await db.commit()

    async def attempt_reserve():
        async with db_session_factory() as db:
            await set_tenant_context(db, str(tenant_id))
            try:
                await quota_service.reserve_space_db(db, tenant_id, 20_000_000)
                await db.commit()
                return True
            except QuotaExceededError:
                await db.rollback()
                return False

    results = await asyncio.gather(*[attempt_reserve() for _ in range(5)])
    assert sum(1 for r in results if r) == 2
    assert sum(1 for r in results if not r) == 3

    async with db_session_factory() as db:
        await set_tenant_context(db, str(tenant_id))
        usage = (await db.execute(select(StorageUsage).where(StorageUsage.tenant_id == tenant_id))).scalar_one()
        assert usage.reserved_bytes == 40_000_000
        assert usage.used_bytes + usage.reserved_bytes <= max_free


@pytest.mark.asyncio
async def test_phase9_pg_e2e_import_clamav_shares_and_pg_dump_restore(
    pg_client: AsyncClient, db_session_factory, pg_harness: _PostgresHarness
):
    await pg_client.post("/api/v1/auth/register", json={
        "email": "e2e_alice@example.com",
        "password": "E2EPassword!2026",
        "full_name": "E2E Alice",
    })
    login = (await pg_client.post("/api/v1/auth/login", json={
        "email": "e2e_alice@example.com",
        "password": "E2EPassword!2026",
    })).json()
    hdr = {"Authorization": f"Bearer {login['access_token']}"}
    tenant_id = uuid.UUID(login["tenant_id"])

    clam_server = _RealTCPClamAVServer()
    await clam_server.start()
    orig_host, orig_port = clamav_scanner.host, clamav_scanner.port
    clamav_scanner.host = clam_server.host
    clamav_scanner.port = clam_server.port

    try:
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        up_ok = await pg_client.post(
            "/api/v1/storage/upload/direct",
            files={"file": ("contrat_reel.pdf", pdf_bytes, "application/pdf")},
            headers=hdr,
        )
        assert up_ok.status_code == 201, up_ok.text
        doc_data = up_ok.json()
        doc_id = doc_data["id"]
        assert doc_data["antivirus_status"] == "CLEAN"
        assert doc_data["sha256_hash"] == hashlib.sha256(pdf_bytes).hexdigest()

        eicar_resp = await pg_client.post(
            "/api/v1/storage/upload/direct",
            files={"file": ("eicar.txt", EICAR_SIGNATURE, "text/plain")},
            headers=hdr,
        )
        assert eicar_resp.status_code == 422

        await clam_server.stop()
        offline_resp = await pg_client.post(
            "/api/v1/storage/upload/direct",
            files={"file": ("offline.pdf", pdf_bytes, "application/pdf")},
            headers=hdr,
        )
        assert offline_resp.status_code == 503

        shr_resp = await pg_client.post(
            "/api/v1/shares/link",
            json={
                "document_id": doc_id,
                "role": "VIEWER",
                "password": "LinkSecretPassword!2026",
                "max_downloads": 2,
                "expires_in_hours": 24,
            },
            headers=hdr,
        )
        assert shr_resp.status_code == 201, shr_resp.text
        raw_token = shr_resp.json()["token"]
        share_id = uuid.UUID(shr_resp.json()["id"])

        async with db_session_factory() as db:
            await set_public_share_context(db, hash_share_token(raw_token))
            share_row = (await db.execute(select(Share).where(Share.id == share_id))).scalar_one()
            assert share_row.token_hash == hash_share_token(raw_token)
            assert raw_token not in share_row.token_hash

        async def pub_dl():
            return await pg_client.post(
                f"/api/v1/shares/public/{raw_token}/download",
                json={"password": "LinkSecretPassword!2026"},
            )

        dl_responses = await asyncio.gather(*[pub_dl() for _ in range(4)])
        codes = [r.status_code for r in dl_responses]
        assert codes.count(200) == 2, f"Exactement 2 téléchargements doivent réussir, obtenu {codes}"
        assert codes.count(403) == 2

        async with db_session_factory() as db:
            logs = (await db.execute(select(AuditLog).where(AuditLog.tenant_id == tenant_id))).scalars().all()
            assert len(logs) >= 3

        rev = await pg_client.delete(f"/api/v1/shares/{share_id}", headers=hdr)
        assert rev.status_code == 200
        after_rev = await pg_client.get(f"/api/v1/shares/public/{raw_token}")
        assert after_rev.status_code == 404

        if not pg_harness.external_url and (PG_BIN / "pg_dump").exists():
            with tempfile.TemporaryDirectory() as bdir:
                dump_path = Path(bdir) / "docuspace.dump"
                subprocess.run(
                    [
                        str(PG_BIN / "pg_dump"),
                        "-h", "127.0.0.1",
                        "-p", str(pg_harness.port),
                        "-U", "pgadmin",
                        "-d", pg_harness.db_name,
                        "-F", "c",
                        "-f", str(dump_path),
                    ],
                    check=True,
                )
                assert dump_path.exists() and dump_path.stat().st_size > 1024
                pg_harness._run_psql("CREATE DATABASE docuspace_restore_test;", db="postgres")
                subprocess.run(
                    [
                        str(PG_BIN / "pg_restore"),
                        "-h", "127.0.0.1",
                        "-p", str(pg_harness.port),
                        "-U", "pgadmin",
                        "-d", "docuspace_restore_test",
                        str(dump_path),
                    ],
                    check=True,
                )
                cnt = subprocess.check_output(
                    [
                        str(PG_BIN / "psql"),
                        "-h", "127.0.0.1",
                        "-p", str(pg_harness.port),
                        "-U", "pgadmin",
                        "-d", "docuspace_restore_test",
                        "-tAc",
                        "SELECT count(*) FROM documents WHERE original_name = 'contrat_reel.pdf';",
                    ],
                    text=True,
                ).strip()
                assert cnt == "1"
    finally:
        clamav_scanner.host, clamav_scanner.port = orig_host, orig_port
        await clam_server.stop()
