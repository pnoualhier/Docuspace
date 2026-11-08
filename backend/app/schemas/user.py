from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: UUID
    tenant_id: UUID

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    tenant_id: Optional[str] = None
    exp: Optional[int] = None
    type: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Minimum 8 caractères")
    full_name: str = Field(min_length=2, max_length=100)

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
