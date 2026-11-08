from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: Optional[UUID] = None
    color: Optional[str] = "#3B82F6"

class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_id: Optional[UUID] = None
    color: Optional[str] = None
    is_favorite: Optional[bool] = None

class FolderRead(BaseModel):
    id: UUID
    tenant_id: UUID
    parent_id: Optional[UUID]
    name: str
    color: str
    is_favorite: bool
    is_trashed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DocumentRead(BaseModel):
    id: UUID
    tenant_id: UUID
    folder_id: Optional[UUID]
    original_name: str
    mime_type: str
    extension: str
    size_bytes: int
    sha256_hash: str
    status: str
    antivirus_status: str
    is_favorite: bool
    is_trashed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DocumentVersionRead(BaseModel):
    id: UUID
    version_number: int
    size_bytes: int
    mime_type: str
    sha256_hash: str
    change_summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
