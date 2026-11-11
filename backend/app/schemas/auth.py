from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: UUID
    tenant_id: UUID
    refresh_token: Optional[str] = None

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    tenant_id: Optional[str] = None
    exp: Optional[int] = None
    type: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None

class SessionRead(BaseModel):
    id: UUID
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    is_revoked: bool
    expires_at: datetime
    created_at: datetime
    last_active_at: datetime

    class Config:
        from_attributes = True

