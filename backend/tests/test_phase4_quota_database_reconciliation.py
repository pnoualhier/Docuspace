import uuid
import pytest
from datetime import datetime, timezone
from backend.app.models.tenant import StorageUsage, Tenant
from backend.app.models.plan import Plan
from backend.app.models.document import Document
from backend.app.services.quota_service import (
    QuotaService,
    QuotaExceededError,
    FileSizeLimitExceededError,
    CANONICAL_PLANS
)

class MockAsyncDbSession:
    """Simulates PostgreSQL AsyncSession with row-level locking for testing."""
    def __init__(self, tenant: Tenant, plan: Plan, storage_usage: StorageUsage, documents: list = None):
        self.tenant = tenant
        self.plan = plan
        self.storage_usage = storage_usage
        self.documents = documents or []
        self.committed = False
        self.locked_for_update = False

    async def execute(self, stmt):
        stmt_str = str(stmt).lower()
        if "for update" in stmt_str:
            self.locked_for_update = True

        class MockResult:
            def __init__(self, outer):
                self.outer = outer

            def first(self):
                if "from tenants" in stmt_str:
                    return (self.outer.tenant, self.outer.plan)
                return None

            def scalar_one_or_none(self):
                if "from storage_usage" in stmt_str:
                    return self.outer.storage_usage
                return None

            def all(self):
                if "from documents" in stmt_str:
                    return self.outer.documents
                return []

        return MockResult(self)

    def add(self, obj):
        pass

    async def flush(self):
        pass

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass

class MockStorageClient:
    def __init__(self, objects: list = None):
        self.objects = objects or []

    def list_objects(self, prefix: str):
        return [obj for obj in self.objects if obj["key"].startswith(prefix)]


def test_phase4_plan_limits_conformance():
    """Verify plan definitions strictly conform to requirements: FREE (500MB), PERSONAL (20GB), PREMIUM (100GB)."""
    assert CANONICAL_PLANS["FREE"]["max_storage_bytes"] == 500 * 1024 * 1024
    assert CANONICAL_PLANS["FREE"]["max_file_size_bytes"] == 100 * 1024 * 1024

    assert CANONICAL_PLANS["PERSONAL"]["max_storage_bytes"] == 20 * 1024 * 1024 * 1024
    assert CANONICAL_PLANS["PERSONAL"]["max_file_size_bytes"] == 2 * 1024 * 1024 * 1024

    assert CANONICAL_PLANS["PREMIUM"]["max_storage_bytes"] == 100 * 1024 * 1024 * 1024
    assert CANONICAL_PLANS["PREMIUM"]["max_file_size_bytes"] == 5 * 1024 * 1024 * 1024


@pytest.mark.asyncio
async def test_phase4_atomic_reservation_and_locking():
    """Verify atomic reservation locks row (FOR UPDATE) and checks capacity against Plan."""
    qs = QuotaService()
    tenant_id = uuid.uuid4()
    plan = Plan(
        id="FREE",
        name="DocuSpace Gratuit",
        max_storage_bytes=500 * 1024 * 1024,
        max_file_size_bytes=100 * 1024 * 1024
    )
    tenant = Tenant(id=tenant_id, name="Test Space", plan_id="FREE", owner_id=uuid.uuid4())
    storage_usage = StorageUsage(tenant_id=tenant_id, used_bytes=0, reserved_bytes=0, document_count=0)
    db = MockAsyncDbSession(tenant, plan, storage_usage)

    # 1. Valid reservation (50 MB)
    file_size = 50 * 1024 * 1024
    res = await qs.check_and_reserve_quota_db(db, tenant_id, file_size)
    assert db.locked_for_update is True
    assert db.committed is True
    assert storage_usage.reserved_bytes == file_size

    # 2. File size exceeding limit (150 MB > 100 MB max_file_size)
    with pytest.raises(FileSizeLimitExceededError):
        await qs.check_and_reserve_quota_db(db, tenant_id, 150 * 1024 * 1024)

    # 3. Total capacity exceeded (used 450 MB + new file 60 MB <= 100 MB max_file, but 450 + 60 = 510 > 500 MB max_storage)
    storage_usage.used_bytes = 450 * 1024 * 1024
    storage_usage.reserved_bytes = 0
    with pytest.raises(QuotaExceededError):
        await qs.check_and_reserve_quota_db(db, tenant_id, 60 * 1024 * 1024)


@pytest.mark.asyncio
async def test_phase4_commit_and_release_lifecycle():
    """Test commit upon clean scan and release on failure/infection."""
    qs = QuotaService()
    tenant_id = uuid.uuid4()
    plan = Plan(id="FREE", name="Free", max_storage_bytes=500*1024*1024, max_file_size_bytes=100*1024*1024)
    tenant = Tenant(id=tenant_id, name="Test Space", plan_id="FREE", owner_id=uuid.uuid4())
    storage_usage = StorageUsage(tenant_id=tenant_id, used_bytes=10*1024*1024, reserved_bytes=20*1024*1024, document_count=1)
    db = MockAsyncDbSession(tenant, plan, storage_usage)

    # Test 1: Successful upload commits 20 MB
    await qs.commit_quota_db(db, tenant_id, 20 * 1024 * 1024)
    assert storage_usage.reserved_bytes == 0
    assert storage_usage.used_bytes == 30 * 1024 * 1024
    assert storage_usage.document_count == 2

    # Test 2: Reserve 15 MB then cancel/fail (infected or MinIO error) -> release
    storage_usage.reserved_bytes = 15 * 1024 * 1024
    await qs.release_reservation_db(db, tenant_id, 15 * 1024 * 1024)
    assert storage_usage.reserved_bytes == 0
    assert storage_usage.used_bytes == 30 * 1024 * 1024 # used bytes unchanged!


@pytest.mark.asyncio
async def test_phase4_minio_postgresql_reconciliation():
    """Verify reconciliation task recalculates usage and detects discrepancies."""
    qs = QuotaService()
    tenant_id = uuid.uuid4()
    plan = Plan(id="FREE", name="Free", max_storage_bytes=500*1024*1024, max_file_size_bytes=100*1024*1024)
    tenant = Tenant(id=tenant_id, name="Test Space", plan_id="FREE", owner_id=uuid.uuid4())
    
    # Active documents in PostgreSQL (2 docs, 15 MB total)
    doc1 = Document(id=uuid.uuid4(), tenant_id=tenant_id, storage_key=f"tenants/{tenant_id}/doc1.pdf", size_bytes=10*1024*1024, is_trashed=False)
    doc2 = Document(id=uuid.uuid4(), tenant_id=tenant_id, storage_key=f"tenants/{tenant_id}/doc2.pdf", size_bytes=5*1024*1024, is_trashed=False)
    
    # Out of sync storage_usage in DB (e.g. following crash, reserved_bytes stuck at 30 MB)
    storage_usage = StorageUsage(tenant_id=tenant_id, used_bytes=8*1024*1024, reserved_bytes=30*1024*1024, document_count=1)
    db = MockAsyncDbSession(tenant, plan, storage_usage, documents=[doc1, doc2])

    # MinIO objects
    storage_client = MockStorageClient(objects=[
        {"key": f"tenants/{tenant_id}/doc1.pdf", "size": 10*1024*1024},
        {"key": f"tenants/{tenant_id}/doc2.pdf", "size": 5*1024*1024},
        {"key": f"tenants/{tenant_id}/orphan_abandoned_upload.bin", "size": 2*1024*1024} # Orphaned
    ])

    report = await qs.reconcile_tenant_storage(db, tenant_id, storage_client)

    # Reconciled values
    assert report.db_document_count == 2
    assert report.db_used_bytes == 15 * 1024 * 1024
    assert storage_usage.used_bytes == 15 * 1024 * 1024
    assert storage_usage.document_count == 2
    assert storage_usage.reserved_bytes == 0 # Stale reservations cleared!
    assert f"tenants/{tenant_id}/orphan_abandoned_upload.bin" in report.orphaned_storage_keys
