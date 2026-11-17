"""
DocuSpace Phase 9 — Real PostgreSQL Integration Tests: Concurrent Quotas, Imports, ClamAV, Shares & Backup Restore
"""
import asyncio
import hashlib
import socketserver
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.core.database import get_db, reset_tenant_context, set_public_share_context, set_tenant_context
from backend.app.main import app
from backend.app.models.audit import AuditLog
from backend.app.models.share import Share
from backend.app.models.tenant import StorageUsage
from backend.app.security.antivirus import EICAR_SIGNATURE, clamav_scanner
from backend.app.security.password import hash_share_token
from backend.app.services.quota_service import QuotaExceededError, quota_service
from backend.tests.pg_harness import PG_BIN, PostgresHarness, find_free_port


class _RealTCPClamAVServer:
    """Real threaded TCP server implementing ClamAV zINSTREAM protocol without blocking event loop."""

    def __init__(self):
        self.host = "127.0.0.1"
        self.port = find_free_port()
        self._server = None
        self._thread = None

    def start(self):
        class _Handler(socketserver.BaseRequestHandler):
            def handle(self):
                try:
                    buf = bytearray()
                    while b"\x00" not in buf:
                        c = self.request.recv(1024)
                        if not c:
                            return
                        buf.extend(c)
                    idx = buf.index(0)
                    if bytes(buf[: idx + 1]) != b"zINSTREAM\x00":
                        return
                    rest = bytearray(buf[idx + 1 :])

                    def read_exact(n: int) -> bytes:
                        while len(rest) < n:
                            m = self.request.recv(4096)
                            if not m:
                                raise EOFError()
                            rest.extend(m)
                        out = bytes(rest[:n])
                        del rest[:n]
                        return out

                    chunks = []
                    while True:
                        sz = int.from_bytes(read_exact(4), "big")
                        if sz == 0:
                            break
                        chunks.append(read_exact(sz))
                    payload = b"".join(chunks)
                    if EICAR_SIGNATURE in payload:
                        self.request.sendall(b"stream: Eicar-Test-Signature FOUND\x00")
                    else:
                        self.request.sendall(b"stream: OK\x00")
                except Exception:
                    pass

        class _TCP(socketserver.ThreadingTCPServer):
            allow_reuse_address = True

        self._server = _TCP((self.host, self.port), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


@pytest.fixture(scope="module")
def pg_harness():
    harness = PostgresHarness("docuspace_p9_ops")
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
async def test_phase9_pg_concurrent_quotas_for_update_locking(pg_client: AsyncClient, db_session_factory):
    await pg_client.post("/api/v1/auth/register", json={
        "email": "quota_race@example.com", "password": "QuotaRacePassword!2026", "full_name": "Quota Race",
    })
    login = (await pg_client.post("/api/v1/auth/login", json={
        "email": "quota_race@example.com", "password": "QuotaRacePassword!2026",
    })).json()
    tenant_id = uuid.UUID(login["tenant_id"])

    max_free = 524_288_000
    async with db_session_factory() as db:
        await set_tenant_context(db, str(tenant_id))
        usage = (await db.execute(select(StorageUsage).where(StorageUsage.tenant_id == tenant_id))).scalar_one()
        usage.used_bytes = max_free - 45_000_000
        usage.reserved_bytes = 0
        await db.commit()

    async def attempt_reserve():
        async with db_session_factory() as db:
            await set_tenant_context(db, str(tenant_id))
            try:
                await quota_service.check_and_reserve_quota_db(db, tenant_id, 20_000_000)
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
async def test_phase9_pg_e2e_import_clamav_shares_and_restore(
    pg_client: AsyncClient, db_session_factory, pg_harness: PostgresHarness
):
    await pg_client.post("/api/v1/auth/register", json={
        "email": "e2e_alice@example.com", "password": "E2EPassword!2026", "full_name": "E2E Alice",
    })
    login = (await pg_client.post("/api/v1/auth/login", json={
        "email": "e2e_alice@example.com", "password": "E2EPassword!2026",
    })).json()
    hdr = {"Authorization": f"Bearer {login['access_token']}"}
    tenant_id = uuid.UUID(login["tenant_id"])

    clam_server = _RealTCPClamAVServer()
    clam_server.start()
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
        resp_json = up_ok.json()
        doc_data = resp_json["document"]
        doc_id = doc_data["id"]
        assert resp_json["antivirus_status"] == "CLEAN"
        assert doc_data["sha256_hash"] == hashlib.sha256(pdf_bytes).hexdigest()

        eicar_resp = await pg_client.post(
            "/api/v1/storage/upload/direct",
            files={"file": ("eicar.txt", EICAR_SIGNATURE, "text/plain")},
            headers=hdr,
        )
        assert eicar_resp.status_code == 422

        clam_server.stop()
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
        assert rev.status_code == 204
        assert (await pg_client.get(f"/api/v1/shares/public/{raw_token}")).status_code == 404

        if not pg_harness.external_url and (PG_BIN / "pg_dump").exists():
            with tempfile.TemporaryDirectory() as bdir:
                dump_path = Path(bdir) / "docuspace.dump"
                subprocess.run(
                    [
                        str(PG_BIN / "pg_dump"), "-h", "127.0.0.1", "-p", str(pg_harness.port),
                        "-U", "pgadmin", "-d", pg_harness.db_name, "-F", "c", "-f", str(dump_path),
                    ],
                    check=True,
                )
                assert dump_path.exists() and dump_path.stat().st_size > 1024
                pg_harness.run_psql("CREATE DATABASE docuspace_restore_test;", db="postgres")
                subprocess.run(
                    [
                        str(PG_BIN / "pg_restore"), "-h", "127.0.0.1", "-p", str(pg_harness.port),
                        "-U", "pgadmin", "-d", "docuspace_restore_test", str(dump_path),
                    ],
                    check=True,
                )
                cnt = subprocess.check_output(
                    [
                        str(PG_BIN / "psql"), "-h", "127.0.0.1", "-p", str(pg_harness.port),
                        "-U", "pgadmin", "-d", "docuspace_restore_test", "-tAc",
                        "SELECT count(*) FROM documents WHERE original_name = 'contrat_reel.pdf';",
                    ],
                    text=True,
                ).strip()
                assert cnt == "1"
    finally:
        clamav_scanner.host, clamav_scanner.port = orig_host, orig_port
        clam_server.stop()
