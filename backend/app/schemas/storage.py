from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from backend.app.schemas.document import DocumentRead

class UploadInitiateRequest(BaseModel):
    original_name: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    mime_type: str = Field(min_length=3, max_length=128)
    folder_id: Optional[UUID] = None

class UploadInitiateResponse(BaseModel):
    session_id: UUID
    upload_url: str
    upload_token: str
    storage_key: str
    headers: Dict[str, str]
    expires_at: int
    max_size_bytes: int

class UploadCompleteRequest(BaseModel):
    session_id: UUID
    sha256_hash: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(gt=0)

class UploadCompleteResponse(BaseModel):
    document: DocumentRead
    antivirus_status: str
    threat_detected: Optional[str] = None
    details: str

class DownloadUrlResponse(BaseModel):
    document_id: UUID
    filename: str
    download_url: str
    expires_in_seconds: int

class QuotaInfoResponse(BaseModel):
    tenant_id: UUID
    max_storage_bytes: int
    used_bytes: int
    reserved_bytes: int
    available_bytes: int
    document_count: int
    usage_percent: float

class ScanReportResponse(BaseModel):
    document_id: UUID
    status: str
    is_clean: bool
    threat_name: Optional[str] = None
    details: Optional[str] = None
    engine: str
