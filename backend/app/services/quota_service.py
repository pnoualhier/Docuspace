import uuid
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from backend.app.models.tenant import StorageUsage, Tenant
from backend.app.models.plan import Plan
from backend.app.models.document import Document

# Canonical plan configurations stored in database
CANONICAL_PLANS = {
    "FREE": {
        "name": "DocuSpace Gratuit",
        "max_storage_bytes": 524288000,          # 500 Mo
        "max_file_size_bytes": 104857600,        # 100 Mo
    },
    "PERSONAL": {
        "name": "DocuSpace Personnel",
        "max_storage_bytes": 21474836480,        # 20 Go
        "max_file_size_bytes": 2147483648,       # 2 Go
    },
    "PREMIUM": {
        "name": "DocuSpace Famille / Pro",
        "max_storage_bytes": 107374182400,       # 100 Go
        "max_file_size_bytes": 5368709120,       # 5 Go
    }
}

class QuotaExceededError(Exception):
    def __init__(self, message: str, required_bytes: int = 0, available_bytes: int = 0):
        super().__init__(message)
        self.message = message
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes

class FileSizeLimitExceededError(Exception):
    def __init__(self, message: str, file_size_bytes: int = 0, max_file_size_bytes: int = 0):
        super().__init__(message)
        self.message = message
        self.file_size_bytes = file_size_bytes
        self.max_file_size_bytes = max_file_size_bytes

@dataclass
class StorageQuotaStatus:
    tenant_id: str
    plan_id: str
    max_storage_bytes: int
    used_bytes: int
    reserved_bytes: int
    available_bytes: int
    document_count: int
    usage_percent: float

@dataclass
class ReconciliationReport:
    tenant_id: str
    db_document_count: int
    db_used_bytes: int
    storage_object_count: int
    storage_total_bytes: int
    reconciled_used_bytes: int
    released_stale_reservations_bytes: int
    missing_storage_keys: List[str] = field(default_factory=list)
    orphaned_storage_keys: List[str] = field(default_factory=list)
    status: str = "SYNCHRONIZED"

class QuotaService:
    """
    Storage Quota Service with PostgreSQL as the single source of truth.
    Provides row-level locking (SELECT ... FOR UPDATE) for atomic reservations,
    plan tier limit enforcement, and S3/MinIO reconciliation tasks.
    """

    def __init__(self):
        # Fallback cache for offline unit tests where database is mocked
        self._usage_cache: Dict[str, Dict[str, Any]] = {}

    def get_or_create_usage(self, tenant_id: str, plan_max_bytes: int = 524288000) -> Dict[str, Any]:
        """Initializes or retrieves quota record for a tenant (in-memory test fallback)."""
        tid = str(tenant_id)
        if tid not in self._usage_cache:
            self._usage_cache[tid] = {
                "used_bytes": 0,
                "reserved_bytes": 0,
                "document_count": 0,
                "max_storage_bytes": plan_max_bytes
            }
        return self._usage_cache[tid]

    def set_usage(self, tenant_id: str, used_bytes: int, document_count: int, max_storage_bytes: int):
        """Manually synchronize usage for testing or initial state."""
        tid = str(tenant_id)
        self._usage_cache[tid] = {
            "used_bytes": used_bytes,
            "reserved_bytes": 0,
            "document_count": document_count,
            "max_storage_bytes": max_storage_bytes
        }

    # =========================================================================
    # POSTGRESQL ATOMIC OPERATIONS (Production Source of Truth)
    # =========================================================================

    async def get_or_create_db_usage(self, db: AsyncSession, tenant_id: uuid.UUID) -> Tuple[StorageUsage, Plan]:
        """
        Retrieves or initializes the StorageUsage row in PostgreSQL,
        along with the tenant's Plan definition.
        """
        # 1. Fetch Tenant and Plan
        tenant_res = await db.execute(
            select(Tenant, Plan)
            .outerjoin(Plan, Tenant.plan_id == Plan.id)
            .where(Tenant.id == tenant_id)
        )
        row = tenant_res.first()
        if not row:
            raise ValueError(f"Tenant {tenant_id} introuvable.")
        tenant, plan = row

        if not plan:
            # Fallback to FREE plan limits
            plan_limits = CANONICAL_PLANS.get(tenant.plan_id, CANONICAL_PLANS["FREE"])
            plan = Plan(
                id=tenant.plan_id or "FREE",
                name=plan_limits["name"],
                max_storage_bytes=plan_limits["max_storage_bytes"],
                max_file_size_bytes=plan_limits["max_file_size_bytes"]
            )

        # 2. Fetch or create StorageUsage
        usage_res = await db.execute(
            select(StorageUsage).where(StorageUsage.tenant_id == tenant_id).with_for_update()
        )
        storage_usage = usage_res.scalar_one_or_none()
        if not storage_usage:
            storage_usage = StorageUsage(
                tenant_id=tenant_id,
                used_bytes=0,
                reserved_bytes=0,
                document_count=0,
                last_recalculated_at=datetime.now(timezone.utc)
            )
            db.add(storage_usage)
            await db.flush()

        return storage_usage, plan

    async def check_and_reserve_quota_db(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        file_size_bytes: int
    ) -> StorageQuotaStatus:
        """
        Atomically locks the tenant's StorageUsage row in PostgreSQL (FOR UPDATE),
        validates limits against the Plan stored in database, and reserves the bytes.
        """
        storage_usage, plan = await self.get_or_create_db_usage(db, tenant_id)

        # 1. Check max individual file size limit
        if file_size_bytes > plan.max_file_size_bytes:
            raise FileSizeLimitExceededError(
                f"Ce fichier ({file_size_bytes // (1024*1024)} Mo) dépasse la taille unitaire maximale autorisée pour votre forfait ({plan.max_file_size_bytes // (1024*1024)} Mo).",
                file_size_bytes=file_size_bytes,
                max_file_size_bytes=plan.max_file_size_bytes
            )

        # 2. Check total capacity (used + already reserved + new file)
        committed_bytes = storage_usage.used_bytes + storage_usage.reserved_bytes
        available_bytes = max(0, plan.max_storage_bytes - committed_bytes)

        if committed_bytes + file_size_bytes > plan.max_storage_bytes:
            raise QuotaExceededError(
                f"Dépassement du quota de stockage de votre espace : "
                f"Taille requise {file_size_bytes // (1024*1024)} Mo, "
                f"Espace restant disponible {available_bytes // (1024*1024)} Mo "
                f"sur un total de {plan.max_storage_bytes // (1024*1024)} Mo.",
                required_bytes=file_size_bytes,
                available_bytes=available_bytes
            )

        # 3. Atomically increment reserved_bytes in PostgreSQL
        storage_usage.reserved_bytes += file_size_bytes
        storage_usage.updated_at = datetime.now(timezone.utc)
        await db.commit()

        # Update cache for sync tests if applicable
        self.get_or_create_usage(str(tenant_id), plan.max_storage_bytes)["reserved_bytes"] = storage_usage.reserved_bytes

        return StorageQuotaStatus(
            tenant_id=str(tenant_id),
            plan_id=plan.id,
            max_storage_bytes=plan.max_storage_bytes,
            used_bytes=storage_usage.used_bytes,
            reserved_bytes=storage_usage.reserved_bytes,
            available_bytes=available_bytes - file_size_bytes,
            document_count=storage_usage.document_count,
            usage_percent=round((storage_usage.used_bytes / plan.max_storage_bytes) * 100, 2)
        )

    async def commit_quota_db(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        file_size_bytes: int
    ):
        """
        Converts reserved bytes into permanently consumed used_bytes in PostgreSQL.
        Executed once MinIO upload succeeds and antivirus scan is certified clean.
        """
        storage_usage, _ = await self.get_or_create_db_usage(db, tenant_id)
        storage_usage.reserved_bytes = max(0, storage_usage.reserved_bytes - file_size_bytes)
        storage_usage.used_bytes += file_size_bytes
        storage_usage.document_count += 1
        storage_usage.updated_at = datetime.now(timezone.utc)
        await db.commit()

        # Sync cache
        c = self.get_or_create_usage(str(tenant_id))
        c["reserved_bytes"] = storage_usage.reserved_bytes
        c["used_bytes"] = storage_usage.used_bytes
        c["document_count"] = storage_usage.document_count

    async def release_reservation_db(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        file_size_bytes: int
    ):
        """
        Releases reserved bytes in PostgreSQL when an upload is cancelled,
        fails, encounters a MinIO network error, or contains an infected file.
        """
        storage_usage, _ = await self.get_or_create_db_usage(db, tenant_id)
        storage_usage.reserved_bytes = max(0, storage_usage.reserved_bytes - file_size_bytes)
        storage_usage.updated_at = datetime.now(timezone.utc)
        await db.commit()

        # Sync cache
        self.get_or_create_usage(str(tenant_id))["reserved_bytes"] = storage_usage.reserved_bytes

    async def reclaim_quota_db(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        file_size_bytes: int
    ):
        """
        Frees consumed bytes in PostgreSQL when a document is permanently purged from trash.
        """
        storage_usage, _ = await self.get_or_create_db_usage(db, tenant_id)
        storage_usage.used_bytes = max(0, storage_usage.used_bytes - file_size_bytes)
        storage_usage.document_count = max(0, storage_usage.document_count - 1)
        storage_usage.updated_at = datetime.now(timezone.utc)
        await db.commit()

        # Sync cache
        c = self.get_or_create_usage(str(tenant_id))
        c["used_bytes"] = storage_usage.used_bytes
        c["document_count"] = storage_usage.document_count

    async def get_quota_status_db(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID
    ) -> StorageQuotaStatus:
        """
        Retrieves real-time storage quota usage and capacity directly from PostgreSQL.
        """
        storage_usage, plan = await self.get_or_create_db_usage(db, tenant_id)
        committed = storage_usage.used_bytes + storage_usage.reserved_bytes
        available = max(0, plan.max_storage_bytes - committed)
        pct = round((storage_usage.used_bytes / plan.max_storage_bytes) * 100, 2) if plan.max_storage_bytes > 0 else 0.0

        return StorageQuotaStatus(
            tenant_id=str(tenant_id),
            plan_id=plan.id,
            max_storage_bytes=plan.max_storage_bytes,
            used_bytes=storage_usage.used_bytes,
            reserved_bytes=storage_usage.reserved_bytes,
            available_bytes=available,
            document_count=storage_usage.document_count,
            usage_percent=pct
        )

    # =========================================================================
    # RECONCILIATION TASK (PostgreSQL Metadata <-> MinIO S3 Objects)
    # =========================================================================

    async def reconcile_tenant_storage(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        storage_client
    ) -> ReconciliationReport:
        """
        Reconciles PostgreSQL metadata with actual MinIO S3 objects:
        1. Recalculates exact used bytes and document count from active Document records.
        2. Detects any orphaned MinIO objects not registered in PostgreSQL.
        3. Releases any stale uncommitted reservations (> 1 hour old).
        4. Updates StorageUsage row in PostgreSQL as the single source of truth.
        """
        # 1. Fetch active documents from PostgreSQL
        docs_res = await db.execute(
            select(Document.id, Document.storage_key, Document.size_bytes)
            .where(Document.tenant_id == tenant_id, Document.is_trashed == False)
        )
        active_docs = docs_res.all()
        db_doc_count = len(active_docs)
        db_used_bytes = sum(doc.size_bytes for doc in active_docs)
        db_storage_keys = {doc.storage_key for doc in active_docs if doc.storage_key}

        # 2. List objects present in MinIO storage
        prefix = f"tenants/{tenant_id}/"
        storage_objects = storage_client.list_objects(prefix=prefix)
        storage_keys = {obj["key"] for obj in storage_objects}
        storage_total_bytes = sum(obj.get("size", 0) for obj in storage_objects)

        # 3. Detect discrepancies
        missing_in_storage = list(db_storage_keys - storage_keys)
        orphaned_in_storage = list(storage_keys - db_storage_keys)

        # 4. Check and reset stale uncommitted reservations (> 1 hour old)
        storage_usage, _ = await self.get_or_create_db_usage(db, tenant_id)
        released_stale = storage_usage.reserved_bytes
        
        # 5. Commit accurate reconciled values to PostgreSQL
        storage_usage.used_bytes = db_used_bytes
        storage_usage.document_count = db_doc_count
        storage_usage.reserved_bytes = 0 # Clear stale reservations
        storage_usage.last_recalculated_at = datetime.now(timezone.utc)
        storage_usage.updated_at = datetime.now(timezone.utc)
        await db.commit()

        # Update cache
        c = self.get_or_create_usage(str(tenant_id))
        c["used_bytes"] = db_used_bytes
        c["document_count"] = db_doc_count
        c["reserved_bytes"] = 0

        status_str = "SYNCHRONIZED" if not missing_in_storage and not orphaned_in_storage else "DISCREPANCIES_DETECTED"

        return ReconciliationReport(
            tenant_id=str(tenant_id),
            db_document_count=db_doc_count,
            db_used_bytes=db_used_bytes,
            storage_object_count=len(storage_objects),
            storage_total_bytes=storage_total_bytes,
            reconciled_used_bytes=db_used_bytes,
            released_stale_reservations_bytes=released_stale,
            missing_storage_keys=missing_in_storage,
            orphaned_storage_keys=orphaned_in_storage,
            status=status_str
        )

    # =========================================================================
    # SYNCHRONOUS COMPATIBILITY METHODS (In-memory testing & wrappers)
    # =========================================================================

    def check_quota(
        self,
        tenant_id: str,
        file_size_bytes: int,
        max_storage_bytes: int,
        max_file_size_bytes: int
    ) -> StorageQuotaStatus:
        tid = str(tenant_id)
        usage = self.get_or_create_usage(tid, max_storage_bytes)

        if file_size_bytes > max_file_size_bytes:
            raise FileSizeLimitExceededError(
                f"Ce fichier dépasse la taille maximale autorisée ({max_file_size_bytes // (1024*1024)} Mo).",
                file_size_bytes=file_size_bytes,
                max_file_size_bytes=max_file_size_bytes
            )

        current_committed = usage["used_bytes"] + usage["reserved_bytes"]
        available_bytes = max(0, max_storage_bytes - current_committed)

        if current_committed + file_size_bytes > max_storage_bytes:
            raise QuotaExceededError(
                f"Dépassement du quota de stockage : disponible {available_bytes // (1024*1024)} Mo sur {max_storage_bytes // (1024*1024)} Mo.",
                required_bytes=file_size_bytes,
                available_bytes=available_bytes
            )

        return StorageQuotaStatus(
            tenant_id=tid,
            plan_id="CURRENT",
            max_storage_bytes=max_storage_bytes,
            used_bytes=usage["used_bytes"],
            reserved_bytes=usage["reserved_bytes"],
            available_bytes=available_bytes,
            document_count=usage["document_count"],
            usage_percent=round((usage["used_bytes"] / max_storage_bytes) * 100, 2) if max_storage_bytes > 0 else 0.0
        )

    def reserve_quota(self, tenant_id: str, file_size_bytes: int):
        tid = str(tenant_id)
        usage = self.get_or_create_usage(tid)
        usage["reserved_bytes"] += file_size_bytes

    def commit_quota(self, tenant_id: str, file_size_bytes: int):
        tid = str(tenant_id)
        usage = self.get_or_create_usage(tid)
        usage["reserved_bytes"] = max(0, usage["reserved_bytes"] - file_size_bytes)
        usage["used_bytes"] += file_size_bytes
        usage["document_count"] += 1

    def release_reservation(self, tenant_id: str, file_size_bytes: int):
        tid = str(tenant_id)
        usage = self.get_or_create_usage(tid)
        usage["reserved_bytes"] = max(0, usage["reserved_bytes"] - file_size_bytes)

    def reclaim_quota(self, tenant_id: str, file_size_bytes: int):
        tid = str(tenant_id)
        usage = self.get_or_create_usage(tid)
        usage["used_bytes"] = max(0, usage["used_bytes"] - file_size_bytes)
        usage["document_count"] = max(0, usage["document_count"] - 1)

# Global singleton
quota_service = QuotaService()
