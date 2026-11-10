from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr

class ShareRecipientRead(BaseModel):
    id: UUID
    recipient_email: str
    recipient_user_id: Optional[UUID] = None
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class InternalShareCreate(BaseModel):
    document_id: Optional[UUID] = None
    folder_id: Optional[UUID] = None
    recipient_email: str = Field(min_length=3, max_length=255)
    role: str = "VIEWER"

class SecureLinkCreate(BaseModel):
    document_id: Optional[UUID] = None
    folder_id: Optional[UUID] = None
    password: Optional[str] = Field(None, min_length=4, max_length=128)
    expires_in_hours: Optional[int] = Field(None, ge=1, le=8760) # up to 1 year
    max_downloads: Optional[int] = Field(None, ge=1)
    role: str = "VIEWER"

class ShareRead(BaseModel):
    id: UUID
    tenant_id: UUID
    document_id: Optional[UUID] = None
    folder_id: Optional[UUID] = None
    target_name: str
    share_type: str # 'INTERNAL_USER' or 'SECURE_LINK'
    role: str
    token: Optional[str] = None
    public_url: Optional[str] = None
    has_password: bool
    max_downloads: Optional[int] = None
    download_count: int = 0
    expires_at: Optional[datetime] = None
    is_active: bool
    is_expired: bool = False
    recipients: List[ShareRecipientRead] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PublicShareAccessRequest(BaseModel):
    password: Optional[str] = None

class PublicShareDetails(BaseModel):
    token: str
    resource_type: str # 'DOCUMENT' or 'FOLDER'
    resource_name: str
    mime_type: Optional[str] = None
    extension: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256_hash: Optional[str] = None
    has_password: bool
    is_password_required: bool
    expires_at: Optional[datetime] = None
    download_count: int
    max_downloads: Optional[int] = None
    can_download: bool
    is_active: bool

class PublicShareDownloadResponse(BaseModel):
    download_url: str
    filename: str
    size_bytes: int
    mime_type: str
    download_count: int
    max_downloads: Optional[int] = None
