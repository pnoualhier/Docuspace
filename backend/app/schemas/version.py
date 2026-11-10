from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class VersionCreate(BaseModel):
    change_summary: Optional[str] = Field("Nouvelle révision", max_length=255)
    size_bytes: int = Field(gt=0)
    sha256_hash: str = Field(min_length=64, max_length=64)
    mime_type: str = Field(min_length=3, max_length=128)

class VersionRead(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    size_bytes: int
    mime_type: str
    sha256_hash: str
    change_summary: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class VersionRestoreResponse(BaseModel):
    document_id: UUID
    restored_version_number: int
    size_bytes: int
    sha256_hash: str
    message: str

class VersionPurgeResponse(BaseModel):
    purged_version_id: UUID
    freed_bytes: int
    remaining_version_count: int
    message: str

class TrashItemRead(BaseModel):
    id: UUID
    item_type: str # 'DOCUMENT' or 'FOLDER'
    name: str
    size_bytes: Optional[int] = None
    trashed_at: datetime
    days_remaining: int
    can_restore: bool = True

class TrashPurgeSummary(BaseModel):
    purged_documents_count: int
    purged_folders_count: int
    freed_bytes: int
    message: str
