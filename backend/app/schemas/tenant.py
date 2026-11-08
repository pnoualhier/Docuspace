from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class PlanRead(BaseModel):
    id: str
    name: str
    max_storage_bytes: int
    max_file_size_bytes: int
    max_members: int
    max_versions_per_file: int
    features: Dict[str, Any]

    class Config:
        from_attributes = True

class StorageUsageRead(BaseModel):
    tenant_id: UUID
    used_bytes: int
    reserved_bytes: int
    document_count: int
    max_storage_bytes: int
    percent_used: float

    class Config:
        from_attributes = True

class TenantRead(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    plan_id: str
    role: str
    is_active: bool
    created_at: datetime
    storage_usage: Optional[StorageUsageRead] = None

    class Config:
        from_attributes = True
