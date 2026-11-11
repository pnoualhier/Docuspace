import uuid
import socket
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException

from backend.app.models.document import Document
from backend.app.models.tenant import StorageUsage
from backend.app.security.antivirus import (
    ClamAVScanner, 
    ScanResult, 
    QuarantineManager, 
    EICAR_SIGNATURE,
    quarantine_manager
)
from backend.app.api.v1.routes.storage import get_download_url
from backend.app.middleware.tenant_context import TenantContext


class MockClamavSocket:
    """Simulates ClamAV daemon TCP responses over socket."""
    def __init__(self, response: bytes = b"stream: OK\0", raise_on_connect=None, raise_on_send=None, raise_on_recv=None):
        self.response = response
        self.raise_on_connect = raise_on_connect
        self.raise_on_send = raise_on_send
        self.raise_on_recv = raise_on_recv
        self.sent_data = b""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def settimeout(self, timeout):
        pass

    def connect(self, addr):
        if self.raise_on_connect:
            raise self.raise_on_connect

    def sendall(self, data):
        if self.raise_on_send:
            raise self.raise_on_send
        self.sent_data += data

    def recv(self, bufsize):
        if self.raise_on_recv:
            raise self.raise_on_recv
        resp = self.response
        self.response = b""
        return resp


class MockStorageClient:
    """Simulates S3 MinIO storage client for quarantine testing."""
    def __init__(self, initial_objects=None):
        self.objects = dict(initial_objects or {})
        self.deleted_keys = []

    def put_object(self, key, data, content_type="application/octet-stream"):
        self.objects[key] = data

    def get_object(self, key):
        if key not in self.objects:
            raise FileNotFoundError(f"Key {key} not found")
        return self.objects[key]

    def delete_object(self, key):
        if key in self.objects:
            del self.objects[key]
        self.deleted_keys.append(key)

    def generate_presigned_download_url(self, storage_key, filename, expires_in=900):
        return f"https://minio.docuspace.local/{storage_key}?Signature=valid_hmac_test"


class MockAsyncDbSession:
    """Mock database session for testing route barriers."""
    def __init__(self, doc: Document = None):
        self.doc = doc

    async def execute(self, stmt):
        class MockResult:
            def __init__(self, doc):
                self._doc = doc
            def scalar_one_or_none(self):
                return self._doc
        return MockResult(self.doc)

    async def commit(self):
        pass

    async def rollback(self):
        pass


# =========================================================================
# TEST 1: ClamAV disponible et analyse positive -> CLEAN
# =========================================================================

def test_phase6_clamav_available_clean():
    """Verify ClamAV daemon responding OK marks file CLEAN with is_clean=True."""
    mock_factory = lambda *a, **k: MockClamavSocket(response=b"stream: OK\0")
    scanner = ClamAVScanner(socket_factory=mock_factory)

    sample_doc = b"%PDF-1.4 Clean business contract content without threats"
    result = scanner.scan_bytes(sample_doc)

    assert result.status == "CLEAN"
    assert result.is_clean is True
    assert result.threat_name is None
    assert "Aucune menace détectée" in result.details


# =========================================================================
# TEST 2: Menace détectée -> INFECTED
# =========================================================================

def test_phase6_threat_detected_infected():
    """Verify ClamAV daemon responding FOUND marks file INFECTED with is_clean=False and parsed threat name."""
    mock_factory = lambda *a, **k: MockClamavSocket(response=b"stream: Win.Trojan.Agent-12345 FOUND\0")
    scanner = ClamAVScanner(socket_factory=mock_factory)

    sample_doc = b"Suspicious binary stream containing trojan payload"
    result = scanner.scan_bytes(sample_doc)

    assert result.status == "INFECTED"
    assert result.is_clean is False
    assert result.threat_name == "Win.Trojan.Agent-12345"
    assert "Menace détectée" in result.details


# =========================================================================
# TEST 3: EICAR Standard Antivirus Test signature -> INFECTED
# =========================================================================

def test_phase6_eicar_standard_signature():
    """Verify standard EICAR test string is detected as INFECTED."""
    scanner = ClamAVScanner()

    # Exact EICAR payload
    res_exact = scanner.scan_bytes(EICAR_SIGNATURE)
    assert res_exact.status == "INFECTED"
    assert res_exact.is_clean is False
    assert "EICAR" in res_exact.threat_name

    # Embedded inside a document
    doc_with_eicar = b"%PDF-1.4 Header\n" + EICAR_SIGNATURE + b"\n%%EOF"
    res_embedded = scanner.scan_bytes(doc_with_eicar)
    assert res_embedded.status == "INFECTED"
    assert res_embedded.is_clean is False
    assert "EICAR" in res_embedded.threat_name


# =========================================================================
# TEST 4: ClamAV indisponible -> SCAN_ERROR (Jamais CLEAN)
# =========================================================================

def test_phase6_clamav_unavailable_scan_error():
    """
    Verify Fail-Closed policy: When ClamAV daemon is unreachable (connection refused),
    the scanner returns SCAN_ERROR with is_clean=False, and NEVER CLEAN.
    """
    mock_factory = lambda *a, **k: MockClamavSocket(
        raise_on_connect=ConnectionRefusedError(111, "Connection refused")
    )
    scanner = ClamAVScanner(socket_factory=mock_factory)

    sample_doc = b"%PDF-1.4 Ordinary business document"
    result = scanner.scan_bytes(sample_doc)

    assert result.status == "SCAN_ERROR"
    assert result.is_clean is False
    assert "indisponible" in result.details.lower() or "connection refused" in result.details.lower()


# =========================================================================
# TEST 5: Timeout ClamAV -> SCAN_ERROR
# =========================================================================

def test_phase6_clamav_timeout_scan_error():
    """Verify socket timeout during ClamAV scan returns SCAN_ERROR with is_clean=False."""
    mock_factory = lambda *a, **k: MockClamavSocket(
        raise_on_recv=socket.timeout("The read operation timed out")
    )
    scanner = ClamAVScanner(socket_factory=mock_factory)

    sample_doc = b"%PDF-1.4 Heavy complex file"
    result = scanner.scan_bytes(sample_doc)

    assert result.status == "SCAN_ERROR"
    assert result.is_clean is False
    assert "timeout" in result.details.lower() or "délai" in result.details.lower()


# =========================================================================
# TEST 6: Réponse invalide ClamAV -> SCAN_ERROR
# =========================================================================

def test_phase6_clamav_invalid_response_scan_error():
    """Verify corrupted or invalid response from daemon returns SCAN_ERROR."""
    mock_factory = lambda *a, **k: MockClamavSocket(response=b"CORRUPTED_GARBAGE_PAYLOAD\0")
    scanner = ClamAVScanner(socket_factory=mock_factory)

    sample_doc = b"%PDF-1.4 Some document"
    result = scanner.scan_bytes(sample_doc)

    assert result.status == "SCAN_ERROR"
    assert result.is_clean is False
    assert "invalide" in result.details.lower() or "corrompue" in result.details.lower()


# =========================================================================
# TEST 7: Erreur de communication / socket error -> SCAN_ERROR
# =========================================================================

def test_phase6_clamav_communication_error_scan_error():
    """Verify broken socket during INSTREAM data transmission returns SCAN_ERROR."""
    mock_factory = lambda *a, **k: MockClamavSocket(
        raise_on_send=ConnectionResetError(104, "Connection reset by peer")
    )
    scanner = ClamAVScanner(socket_factory=mock_factory)

    sample_doc = b"%PDF-1.4 Test stream failure"
    result = scanner.scan_bytes(sample_doc)

    assert result.status == "SCAN_ERROR"
    assert result.is_clean is False
    assert "erreur de communication" in result.details.lower() or "reset" in result.details.lower()


# =========================================================================
# TEST 8: Quarantaine isolée
# =========================================================================

def test_phase6_quarantine_isolation():
    """Verify QuarantineManager isolates infected file, removes from tenant path, and tracks record."""
    qm = QuarantineManager()
    tenant_id = uuid.uuid4()
    original_key = f"tenants/{tenant_id}/sample_file.pdf"
    infected_payload = b"Infected payload content"

    storage = MockStorageClient({
        original_key: infected_payload
    })

    record = qm.quarantine_file(
        storage_client=storage,
        tenant_id=tenant_id,
        storage_key=original_key,
        original_name="sample_file.pdf",
        threat_name="Win.Malware.Agent",
        content=infected_payload
    )

    # 1. Original file deleted from tenant path
    assert original_key not in storage.objects
    assert original_key in storage.deleted_keys

    # 2. File stored in isolated quarantine path
    quarantine_key = record["quarantine_key"]
    assert quarantine_key.startswith(f"quarantine/{tenant_id}/")
    assert quarantine_key in storage.objects
    assert storage.objects[quarantine_key] == infected_payload

    # 3. Registry tracking
    records = qm.list_quarantined_files(tenant_id)
    assert len(records) == 1
    assert records[0]["threat_name"] == "Win.Malware.Agent"
    assert records[0]["original_name"] == "sample_file.pdf"


# =========================================================================
# TEST 9: Barrière de téléchargement : Aucun fichier non analysé disponible
# =========================================================================

@pytest.mark.asyncio
async def test_phase6_download_barrier_for_non_clean_documents():
    """
    Verify: Aucun fichier non analysé (PENDING, SCAN_ERROR) ou INFECTED
    ne doit être rendu disponible au téléchargement.
    Only CLEAN allows generating a download URL.
    """
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    class FakeContext:
        def __init__(self, t_id, u_id):
            self.tenant_id = t_id
            self.user_id = u_id
            class TenantObj:
                id = t_id
            self.tenant = TenantObj()
            class UserObj:
                id = u_id
            self.user = UserObj()

    ctx = FakeContext(tenant_id, user_id)

    # 1. Document INFECTED -> HTTP 403 Forbidden
    doc_infected = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        original_name="virus.pdf",
        storage_key=f"tenants/{tenant_id}/virus.pdf",
        mime_type="application/pdf",
        extension="pdf",
        size_bytes=1024,
        sha256_hash="dummyhash",
        status="QUARANTINED",
        antivirus_status="INFECTED",
        antivirus_details="Menace Win.Trojan",
        is_trashed=False,
        created_by=user_id
    )
    db_infected = MockAsyncDbSession(doc_infected)

    with pytest.raises(HTTPException) as exc_infected:
        await get_download_url(doc_infected.id, context=ctx, db=db_infected)
    assert exc_infected.value.status_code == 403
    assert "quarantaine" in exc_infected.value.detail.lower()

    # 2. Document SCAN_ERROR (not analyzed / error) -> HTTP 423 Locked
    doc_error = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        original_name="unverified.pdf",
        storage_key=f"tenants/{tenant_id}/unverified.pdf",
        mime_type="application/pdf",
        extension="pdf",
        size_bytes=1024,
        sha256_hash="dummyhash2",
        status="READY",
        antivirus_status="SCAN_ERROR",
        antivirus_details="ClamAV daemon offline",
        is_trashed=False,
        created_by=user_id
    )
    db_error = MockAsyncDbSession(doc_error)

    with pytest.raises(HTTPException) as exc_error:
        await get_download_url(doc_error.id, context=ctx, db=db_error)
    assert exc_error.value.status_code == 423
    assert "statut antivirus" in exc_error.value.detail.lower()

    # 3. Document PENDING -> HTTP 423 Locked
    doc_pending = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        original_name="pending.pdf",
        storage_key=f"tenants/{tenant_id}/pending.pdf",
        mime_type="application/pdf",
        extension="pdf",
        size_bytes=1024,
        sha256_hash="dummyhash3",
        status="READY",
        antivirus_status="PENDING",
        is_trashed=False,
        created_by=user_id
    )
    db_pending = MockAsyncDbSession(doc_pending)

    with pytest.raises(HTTPException) as exc_pending:
        await get_download_url(doc_pending.id, context=ctx, db=db_pending)
    assert exc_pending.value.status_code == 423

    # 4. Document CLEAN -> Permitted with presigned URL
    doc_clean = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        original_name="facture_clean.pdf",
        storage_key=f"tenants/{tenant_id}/facture_clean.pdf",
        mime_type="application/pdf",
        extension="pdf",
        size_bytes=1024,
        sha256_hash="dummyhash4",
        status="READY",
        antivirus_status="CLEAN",
        antivirus_details="Analysé avec succès",
        is_trashed=False,
        created_by=user_id
    )
    db_clean = MockAsyncDbSession(doc_clean)

    resp = await get_download_url(doc_clean.id, context=ctx, db=db_clean)
    assert resp.document_id == doc_clean.id
    assert resp.download_url is not None
    assert "Signature=" in resp.download_url
