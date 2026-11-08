from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import get_db
from backend.app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from backend.app.models.user import User, Session
from backend.app.models.tenant import Tenant, TenantMember, StorageUsage
from backend.app.schemas.user import UserRead, RegisterRequest, LoginRequest
from backend.app.schemas.auth import Token
from backend.app.middleware.tenant_context import get_current_user

router = APIRouter()

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED, tags=["Authentification"])
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Registers a new user and automatically provisions their personal isolated document tenant
    inside a single atomic database transaction.
    """
    existing_user = await db.execute(select(User).where(User.email == payload.email.lower()))
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Une adresse e-mail identique est déjà enregistrée"
        )

    # 1. Create User
    new_user = User(
        email=payload.email.lower(),
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        is_active=True,
        is_verified=True # Auto-verify for standard flow
    )
    db.add(new_user)
    await db.flush()

    # 2. Automatically provision Personal Tenant
    tenant_name = f"Espace de {payload.full_name}"
    personal_tenant = Tenant(
        name=tenant_name,
        owner_id=new_user.id,
        plan_id="FREE",
        is_active=True
    )
    db.add(personal_tenant)
    await db.flush()

    # 3. Associate as OWNER
    membership = TenantMember(
        tenant_id=personal_tenant.id,
        user_id=new_user.id,
        role="OWNER"
    )
    db.add(membership)

    # 4. Initialize Storage Usage Quota Tracker
    storage = StorageUsage(
        tenant_id=personal_tenant.id,
        used_bytes=0,
        reserved_bytes=0,
        document_count=0
    )
    db.add(storage)

    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token, tags=["Authentification"])
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Authenticates a user with Argon2id and generates JWT tokens.
    Sets HttpOnly cookie for web security and returns Bearer token.
    """
    query = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = query.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte utilisateur est suspendu"
        )

    # Fetch default tenant
    tenant_query = await db.execute(
        select(Tenant).where(Tenant.owner_id == user.id, Tenant.is_active == True).limit(1)
    )
    tenant = tenant_query.scalar_one_or_none()
    tenant_id = tenant.id if tenant else user.id

    access_token = create_access_token(subject=str(user.id), tenant_id=str(tenant_id))
    refresh_token = create_refresh_token(subject=str(user.id))

    # Set secure HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False, # Set True in SSL production
        max_age=1800
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=1800,
        user_id=user.id,
        tenant_id=tenant_id
    )

@router.post("/logout", tags=["Authentification"])
async def logout(response: Response, current_user: User = Depends(get_current_user)):
    """Logs out user and clears HttpOnly session cookies."""
    response.delete_cookie(key="access_token")
    return {"message": "Déconnexion réussie"}

@router.get("/me", response_model=UserRead, tags=["Authentification"])
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns authenticated user profile."""
    return current_user
