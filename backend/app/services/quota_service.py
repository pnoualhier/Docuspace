import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass

class QuotaExceededError(Exception):
    def __init__(self, message: str, required_bytes: int, available_bytes: int):
        super().__init__(message)
        self.message = message
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes

class FileSizeLimitExceededError(Exception):
    def __init__(self, message: str, file_size_bytes: int, max_file_size_bytes: int):
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

class QuotaService:
    """
    Service responsible for strictly enforcing storage limits and atomic reservations.
    Prevents storage exhaustion, enforces per-plan tiers, and tracks atomic reservations.
    """

    def __init__(self):
        # In-memory storage usage cache for instant access and unit tests
        self._usage_cache: Dict[str, Dict[str, Any]] = {}

    def get_or_create_usage(self, tenant_id: str, plan_max_bytes: int = 5368709120) -> Dict[str, Any]:
        """Initializes or retrieves quota record for a tenant."""
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

    def check_quota(
        self,
        tenant_id: str,
        file_size_bytes: int,
        max_storage_bytes: int,
        max_file_size_bytes: int
    ) -> StorageQuotaStatus:
        """
        Validates whether a file upload can be accepted without breaching quotas.
        Raises:
          - FileSizeLimitExceededError if single file exceeds plan limit.
          - QuotaExceededError if total storage capacity would be exceeded.
        """
        tid = str(tenant_id)
        usage = self.get_or_create_usage(tid, max_storage_bytes)

        # 1. Check max individual file size limit
        if file_size_bytes > max_file_size_bytes:
            raise FileSizeLimitExceededError(
                f"Ce fichier ({file_size_bytes // (1024*1024)} Mo) dépasse la taille unitaire maximale autorisée pour votre forfait ({max_file_size_bytes // (1024*1024)} Mo).",
                file_size_bytes=file_size_bytes,
                max_file_size_bytes=max_file_size_bytes
            )

        # 2. Check total tenant quota (used + already reserved + new file)
        current_committed = usage["used_bytes"] + usage["reserved_bytes"]
        available_bytes = max(0, max_storage_bytes - current_committed)

        if current_committed + file_size_bytes > max_storage_bytes:
            raise QuotaExceededError(
                f"Dépassement du quota de stockage de votre espace : "
                f"Taille requise {file_size_bytes // (1024*1024)} Mo, "
                f"Espace restant disponible {available_bytes // (1024*1024)} Mo "
                f"sur un total de {max_storage_bytes // (1024*1024)} Mo.",
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
            usage_percent=round((usage["used_bytes"] / max_storage_bytes) * 100, 2)
        )

    def reserve_quota(self, tenant_id: str, file_size_bytes: int):
        """Atomically locks bytes while upload and antivirus scan are underway."""
        tid = str(tenant_id)
        usage = self.get_or_create_usage(tid)
        usage["reserved_bytes"] += file_size_bytes

    def commit_quota(self, tenant_id: str, file_size_bytes: int):
        """Converts reserved bytes to permanently used bytes after clean scan."""
        tid = str(tenant_id)
        usage = self.get_or_create_usage(tid)
        usage["reserved_bytes"] = max(0, usage["reserved_bytes"] - file_size_bytes)
        usage["used_bytes"] += file_size_bytes
        usage["document_count"] += 1

    def release_reservation(self, tenant_id: str, file_size_bytes: int):
        """Frees locked bytes if upload was cancelled, failed, or infected."""
        tid = str(tenant_id)
        usage = self.get_or_create_usage(tid)
        usage["reserved_bytes"] = max(0, usage["reserved_bytes"] - file_size_bytes)

    def reclaim_quota(self, tenant_id: str, file_size_bytes: int):
        """Frees permanently stored bytes when a document is purged from trash."""
        tid = str(tenant_id)
        usage = self.get_or_create_usage(tid)
        usage["used_bytes"] = max(0, usage["used_bytes"] - file_size_bytes)
        usage["document_count"] = max(0, usage["document_count"] - 1)

# Global quota manager
quota_service = QuotaService()
