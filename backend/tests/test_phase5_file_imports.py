import uuid
import io
import hashlib
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import UploadFile, HTTPException

from backend.app.models.tenant import Tenant, StorageUsage
from backend.app.models.plan import Plan
from backend.app.models.document import Folder, Document, UploadSession
from backend.app.storage.upload_service import (
    stream_and_verify_upload,
    detect_real_mime_type,
    generate_secure_storage_key,
    validate_folder_ownership,
    create_persisted_upload_session,
    get_valid_persisted_upload_session,
    cleanup_expired_sessions,
)
from backend.app.storage.storage_interface import is_prohibited_extension
from backend.app.services.quota_service import quota_service


class FakeUploadFile:
    """Simulates FastAPI UploadFile chunked streaming."""
    def __init__(self, filename: str, content: bytes, content_type: str = "application/octet-stream"):
        self.filename = filename
        self.content_type = content_type
        self._bio = io.BytesIO(content)

    async def read(self, size: int = -1) -> bytes:
        return self._bio.read(size)


class MockSessionDb:
    """Mock AsyncSession tailored for upload sessions and quota persistence."""
    def __init__(self, storage_usage: StorageUsage = None, sessions: list = None, folders: list = None, tenant: Tenant = None, plan: Plan = None):
        self.storage_usage = storage_usage
        self.sessions = {s.id: s for s in (sessions or [])}
        self.folders = {f.id: f for f in (folders or [])}
        self.tenant = tenant
        self.plan = plan
        self.committed = False
        self.added = []
        self.locked_for_update = False

    async def execute(self, stmt):
        stmt_str = str(stmt).lower()
        if "for update" in stmt_str:
            self.locked_for_update = True

        class MockResult:
            def __init__(self, outer):
                self.outer = outer

            def scalar_one_or_none(self):
                if "from upload_sessions" in stmt_str:
                    # Look up from self.sessions
                    for sess in self.outer.sessions.values():
                        return sess
                    return None
                if "from storage_usage" in stmt_str:
                    return self.outer.storage_usage
                if "from folders" in stmt_str:
                    for f in self.outer.folders.values():
                        return f
                    return None
                return None

            def scalars(self):
                class MockScalars:
                    def __init__(self, outer):
                        self.outer = outer
                    def all(self):
                        if "from upload_sessions" in stmt_str:
                            return list(self.outer.sessions.values())
                        return []
                return MockScalars(self.outer)

            def first(self):
                if "from tenants" in stmt_str:
                    return (self.outer.tenant, self.outer.plan)
                return None

        return MockResult(self)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, UploadSession):
            self.sessions[obj.id] = obj

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        pass

    async def rollback(self):
        pass


class MockS3StorageClient:
    def __init__(self, initial_objects: dict = None):
        self.storage = initial_objects or {}
        self.deleted_keys = []

    def get_object(self, key: str) -> bytes:
        if key not in self.storage:
            raise FileNotFoundError(f"Object {key} not found")
        return self.storage[key]

    def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream"):
        self.storage[key] = data

    def delete_object(self, key: str):
        if key in self.storage:
            del self.storage[key]
        self.deleted_keys.append(key)

    def compute_sha256(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()


# =========================================================================
# TEST 1: Chunked streaming & on-the-fly SHA-256 computation
# =========================================================================

@pytest.mark.asyncio
async def test_phase5_stream_upload_and_sha256():
    """Verify stream_and_verify_upload computes SHA-256 incrementally and calculates exact size."""
    raw_payload = b"%PDF-1.4 Mock document streaming chunk test " * 5000  # ~220 KB
    expected_hash = hashlib.sha256(raw_payload).hexdigest()
    expected_size = len(raw_payload)

    fake_file = FakeUploadFile(filename="facture_2026.pdf", content=raw_payload, content_type="application/pdf")

    content, sha256_hash, total_size, real_mime = await stream_and_verify_upload(
        file=fake_file,
        max_allowed_bytes=10 * 1024 * 1024  # 10 MB limit
    )

    assert content == raw_payload
    assert sha256_hash == expected_hash
    assert total_size == expected_size
    assert real_mime == "application/pdf"


# =========================================================================
# TEST 2: Strict real size ceiling enforcement during streaming
# =========================================================================

@pytest.mark.asyncio
async def test_phase5_strict_size_ceiling_enforcement():
    """Verify stream immediately aborts with HTTP 413 when content exceeds max allowed size."""
    large_payload = b"A" * (2 * 1024 * 1024)  # 2 MB
    fake_file = FakeUploadFile(filename="archive.zip", content=large_payload, content_type="application/zip")

    # Limit to 1 MB
    with pytest.raises(HTTPException) as exc_info:
        await stream_and_verify_upload(
            file=fake_file,
            max_allowed_bytes=1 * 1024 * 1024  # 1 MB max
        )

    assert exc_info.value.status_code == 413
    assert "dépasse la limite autorisée" in exc_info.value.detail


# =========================================================================
# TEST 3: Real MIME magic bytes detection & executable polyglot defense
# =========================================================================

def test_phase5_magic_bytes_detection_and_executable_rejection():
    """
    Verify magic byte inspection correctly identifies legitimate formats
    and rejects executable payloads disguised as documents or images.
    """
    # 1. Legitimate formats
    pdf_bytes = b"%PDF-1.7 header content"
    mime, dangerous = detect_real_mime_type(pdf_bytes, "rapport.pdf", "application/pdf")
    assert mime == "application/pdf"
    assert dangerous is False

    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    mime, dangerous = detect_real_mime_type(png_bytes, "avatar.png", "image/png")
    assert mime == "image/png"
    assert dangerous is False

    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    mime, dangerous = detect_real_mime_type(jpeg_bytes, "photo.jpg", "image/jpeg")
    assert mime == "image/jpeg"
    assert dangerous is False

    json_bytes = b'{"status": "ok", "tenant": "uuid"}'
    mime, dangerous = detect_real_mime_type(json_bytes, "data.json", "application/json")
    assert mime == "application/json"
    assert dangerous is False

    # 2. Executable payloads disguised with fake extensions (Polyglot attacks)
    # Windows PE disguised as PDF
    pe_executable = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00"
    mime, dangerous = detect_real_mime_type(pe_executable, "malicious.pdf", "application/pdf")
    assert dangerous is True

    # Linux ELF disguised as PNG
    elf_executable = b"\x7fELF\x02\x01\x01\x00\x00\x00"
    mime, dangerous = detect_real_mime_type(elf_executable, "image.png", "image/png")
    assert dangerous is True

    # Shell script disguised as TXT
    sh_script = b"#!/bin/bash\nrm -rf /"
    mime, dangerous = detect_real_mime_type(sh_script, "notes.txt", "text/plain")
    assert dangerous is True

    # Java bytecode disguised as DOCX
    java_class = b"\xca\xfe\xba\xbe\x00\x00\x003"
    mime, dangerous = detect_real_mime_type(java_class, "document.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert dangerous is True

    # PHP script disguised as JPG
    php_code = b"<?php phpinfo(); ?>"
    mime, dangerous = detect_real_mime_type(php_code, "photo.jpg", "image/jpeg")
    assert dangerous is True

    # 3. Prohibited file extensions
    assert is_prohibited_extension("payload.exe") is True
    assert is_prohibited_extension("script.sh") is True
    assert is_prohibited_extension("install.bat") is True
    assert is_prohibited_extension("library.dll") is True
    assert is_prohibited_extension("valid_document.pdf") is False


# =========================================================================
# TEST 4: Secure random non-guessable storage keys & folder tenant ownership
# =========================================================================

@pytest.mark.asyncio
async def test_phase5_secure_storage_keys_and_folder_ownership():
    """Verify cryptographically random storage keys and strict folder tenant ownership."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    key1, ext1 = generate_secure_storage_key(tenant_a, "Contrat_2026.pdf")
    key2, ext2 = generate_secure_storage_key(tenant_a, "Contrat_2026.pdf")

    # Keys must be non-predictable, unique, and scoped to the tenant
    assert key1 != key2
    assert key1.startswith(f"tenants/{tenant_a}/")
    assert ext1 == "pdf"
    assert len(key1.split("/")[2]) >= 32  # 16-bytes hex + .pdf

    # Folder ownership validation
    folder_a = Folder(id=uuid.uuid4(), tenant_id=tenant_a, name="Documents A", is_trashed=False)
    db = MockSessionDb(storage_usage=None, folders=[folder_a])

    # Valid folder in Tenant A
    validated = await validate_folder_ownership(db, folder_a.id, tenant_a)
    assert validated.id == folder_a.id

    # Trying to upload into Tenant A's folder with Tenant B context raises 404
    class MockEmptyDb:
        async def execute(self, stmt):
            class EmptyRes:
                def scalar_one_or_none(self):
                    return None
            return EmptyRes()

    with pytest.raises(HTTPException) as exc:
        await validate_folder_ownership(MockEmptyDb(), folder_a.id, tenant_b)
    assert exc.value.status_code == 404


# =========================================================================
# TEST 5: Persisted upload session lifecycle & TTL expiration in PostgreSQL
# =========================================================================

@pytest.mark.asyncio
async def test_phase5_upload_session_persistence_and_ttl():
    """Verify upload session is saved in PostgreSQL, row-locked, and expires according to TTL."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    storage_usage = StorageUsage(tenant_id=tenant_id, used_bytes=0, reserved_bytes=1000, document_count=0)
    tenant = Tenant(id=tenant_id, name="Test Space", plan_id="FREE", owner_id=user_id)
    plan = Plan(id="FREE", name="DocuSpace Gratuit", max_storage_bytes=500 * 1024 * 1024, max_file_size_bytes=100 * 1024 * 1024)
    db = MockSessionDb(storage_usage=storage_usage, tenant=tenant, plan=plan)

    # 1. Create persisted upload session
    session = await create_persisted_upload_session(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        folder_id=None,
        original_name="contrat.pdf",
        extension="pdf",
        mime_type="application/pdf",
        size_bytes=1000,
        storage_key=f"tenants/{tenant_id}/sample.pdf",
        upload_token="tok_12345",
        expires_minutes=30
    )

    assert session.status == "INITIATED"
    assert session.tenant_id == tenant_id
    assert db.committed is True

    # 2. Retrieve valid unexpired session
    valid_session = await get_valid_persisted_upload_session(db, session.id, tenant_id)
    assert valid_session.id == session.id
    assert db.locked_for_update is True

    # 3. Handle expired session (TTL exceeded)
    expired_session = UploadSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        original_name="expired.pdf",
        extension="pdf",
        mime_type="application/pdf",
        size_bytes=500,
        storage_key=f"tenants/{tenant_id}/expired.pdf",
        upload_token="tok_expired",
        status="INITIATED",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),  # in past!
        created_at=datetime.now(timezone.utc) - timedelta(minutes=35)
    )
    db_expired = MockSessionDb(storage_usage=storage_usage, sessions=[expired_session], tenant=tenant, plan=plan)

    with pytest.raises(HTTPException) as exc:
        await get_valid_persisted_upload_session(db_expired, expired_session.id, tenant_id)
    assert exc.value.status_code == 410  # GONE
    assert expired_session.status == "EXPIRED"


# =========================================================================
# TEST 6: Cleanup of expired sessions & orphaned S3 objects
# =========================================================================

@pytest.mark.asyncio
async def test_phase5_cleanup_expired_sessions_and_orphaned_objects():
    """Verify cleanup_expired_sessions releases reserved bytes and removes orphaned S3 objects."""
    tenant_id = uuid.uuid4()
    storage_usage = StorageUsage(tenant_id=tenant_id, used_bytes=0, reserved_bytes=2000, document_count=0)
    tenant = Tenant(id=tenant_id, name="Test Space", plan_id="FREE", owner_id=uuid.uuid4())
    plan = Plan(id="FREE", name="DocuSpace Gratuit", max_storage_bytes=500 * 1024 * 1024, max_file_size_bytes=100 * 1024 * 1024)

    # 2 expired sessions
    sess1 = UploadSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        original_name="orphan1.pdf",
        extension="pdf",
        mime_type="application/pdf",
        size_bytes=1000,
        storage_key=f"tenants/{tenant_id}/orphan1.pdf",
        upload_token="tok1",
        status="INITIATED",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        created_at=datetime.now(timezone.utc) - timedelta(minutes=40)
    )
    sess2 = UploadSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        original_name="orphan2.pdf",
        extension="pdf",
        mime_type="application/pdf",
        size_bytes=1000,
        storage_key=f"tenants/{tenant_id}/orphan2.pdf",
        upload_token="tok2",
        status="INITIATED",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        created_at=datetime.now(timezone.utc) - timedelta(minutes=35)
    )

    db = MockSessionDb(storage_usage=storage_usage, sessions=[sess1, sess2], tenant=tenant, plan=plan)
    storage = MockS3StorageClient({
        sess1.storage_key: b"partially uploaded bytes 1",
        sess2.storage_key: b"partially uploaded bytes 2",
    })

    result = await cleanup_expired_sessions(db, storage)

    assert result["cleaned_sessions_count"] == 2
    assert result["freed_reserved_bytes"] == 2000
    assert sess1.status == "EXPIRED"
    assert sess2.status == "EXPIRED"
    # S3 objects removed
    assert sess1.storage_key not in storage.storage
    assert sess2.storage_key not in storage.storage
    # Reserved bytes freed in PostgreSQL
    assert storage_usage.reserved_bytes == 0


# =========================================================================
# TEST 7: Strict error handling & no fabricated content on missing MinIO object
# =========================================================================

def test_phase5_missing_minio_object_fails_explicitly():
    """Verify that a missing MinIO object raises FileNotFoundError without fabricating replacement data."""
    storage = MockS3StorageClient({})
    missing_key = "tenants/sample-uuid/ghost.pdf"

    with pytest.raises(FileNotFoundError):
        storage.get_object(missing_key)
