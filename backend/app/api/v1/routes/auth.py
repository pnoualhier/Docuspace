import uuid
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Query, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from jose import JWTError

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)
from backend.app.models.user import User, Session
from backend.app.models.tenant import Tenant, TenantMember, StorageUsage
from backend.app.schemas.user import (
    UserRead,
    RegisterRequest,
    LoginRequest,
    PasswordResetRequest,
    PasswordResetConfirm
)
from backend.app.schemas.auth import Token, RefreshTokenRequest, SessionRead
from backend.app.middleware.tenant_context import get_current_user

router = APIRouter()

# In-memory rate limiter for failed login attempts to prevent brute force & account enumeration
_LOGIN_ATTEMPTS: Dict[str, List[datetime]] = {}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_WINDOW_MINUTES = 15

def _is_rate_limited(identifier: str) -> bool:
    now = datetime.now(timezone.utc)
    window = now - timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
    attempts = [t for t in _LOGIN_ATTEMPTS.get(identifier, []) if t > window]
    _LOGIN_ATTEMPTS[identifier] = attempts
    return len(attempts) >= MAX_LOGIN_ATTEMPTS

def _record_failed_attempt(identifier: str):
    now = datetime.now(timezone.utc)
    if identifier not in _LOGIN_ATTEMPTS:
        _LOGIN_ATTEMPTS[identifier] = []
    _LOGIN_ATTEMPTS[identifier].append(now)

def _reset_attempts(identifier: str):
    _LOGIN_ATTEMPTS.pop(identifier, None)

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

    verification_token = secrets.token_urlsafe(32)
    verification_expires = datetime.now(timezone.utc) + timedelta(hours=24)

    # 1. Create User
    new_user = User(
        email=payload.email.lower(),
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        is_active=True,
        is_verified=True, # Pre-verified for standard setup; token stored for audit/validation
        verification_token=verification_token,
        verification_token_expires_at=verification_expires
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

@router.get("/verify-email", tags=["Authentification"])
async def verify_email(token: str = Query(..., description="Jeton de vérification e-mail"), db: AsyncSession = Depends(get_db)):
    """Valide l'adresse e-mail de l'utilisateur via son jeton de vérification."""
    user_res = await db.execute(
        select(User).where(User.verification_token == token)
    )
    user = user_res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if not user or (user.verification_token_expires_at and user.verification_token_expires_at < now):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jeton de vérification invalide ou expiré."
        )

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires_at = None
    await db.commit()

    return {"message": "Adresse e-mail vérifiée avec succès."}

@router.post("/login", response_model=Token, tags=["Authentification"])
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticates a user with Argon2id and generates JWT tokens.
    Persists active session in PostgreSQL and sets HttpOnly cookies.
    Enforces brute-force rate-limiting and anti account-enumeration.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    rate_limit_key = f"{client_ip}:{payload.email.lower()}"

    if _is_rate_limited(rate_limit_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Trop de tentatives de connexion échouées. Compte temporairement bloqué pendant {LOCKOUT_WINDOW_MINUTES} minutes."
        )

    query = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = query.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        _record_failed_attempt(rate_limit_key)
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

    _reset_attempts(rate_limit_key)

    # Fetch default owned tenant
    tenant_query = await db.execute(
        select(Tenant).where(Tenant.owner_id == user.id, Tenant.is_active == True).limit(1)
    )
    tenant = tenant_query.scalar_one_or_none()
    tenant_id = tenant.id if tenant else user.id

    access_token = create_access_token(subject=str(user.id), tenant_id=str(tenant_id))
    refresh_token = create_refresh_token(subject=str(user.id))

    # Persist session in PostgreSQL
    refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    user_agent = request.headers.get("user-agent", "")[:512]
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    session_record = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        user_agent=user_agent,
        ip_address=client_ip,
        is_revoked=False,
        expires_at=expires_at,
        created_at=now,
        last_active_at=now
    )
    db.add(session_record)
    await db.commit()

    is_secure = settings.APP_ENV == "production"

    # Set secure HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=1800
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=86400 * settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=1800,
        user_id=user.id,
        tenant_id=tenant_id,
        refresh_token=refresh_token
    )

@router.post("/refresh", response_model=Token, tags=["Authentification"])
async def refresh_access_token(
    response: Response,
    request: Request,
    payload: Optional[RefreshTokenRequest] = None,
    refresh_cookie: Optional[str] = Cookie(None, alias="refresh_token"),
    db: AsyncSession = Depends(get_db)
):
    """
    Refreshes an access token with rotation and revocation of previous refresh session.
    """
    token_str = None
    if payload and payload.refresh_token:
        token_str = payload.refresh_token
    elif refresh_cookie:
        token_str = refresh_cookie

    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton de rafraîchissement manquant."
        )

    try:
        decoded = decode_token(token_str)
        if decoded.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Type de jeton invalide")
        user_id = uuid.UUID(decoded.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton de rafraîchissement expiré ou invalide")

    token_hash = hashlib.sha256(token_str.encode()).hexdigest()
    session_res = await db.execute(
        select(Session).where(
            Session.user_id == user_id,
            Session.refresh_token_hash == token_hash,
            Session.is_revoked == False
        )
    )
    current_session = session_res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if not current_session or current_session.expires_at < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expirée ou révoquée")

    # Rotate session: revoke old session
    current_session.is_revoked = True

    # Fetch default tenant
    tenant_query = await db.execute(
        select(Tenant).where(Tenant.owner_id == user_id, Tenant.is_active == True).limit(1)
    )
    tenant = tenant_query.scalar_one_or_none()
    tenant_id = tenant.id if tenant else user_id

    new_access_token = create_access_token(subject=str(user_id), tenant_id=str(tenant_id))
    new_refresh_token = create_refresh_token(subject=str(user_id))
    new_refresh_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()

    client_ip = request.client.host if request.client else "127.0.0.1"
    new_session = Session(
        id=uuid.uuid4(),
        user_id=user_id,
        refresh_token_hash=new_refresh_hash,
        user_agent=request.headers.get("user-agent", "")[:512],
        ip_address=client_ip,
        is_revoked=False,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        created_at=now,
        last_active_at=now
    )
    db.add(new_session)
    await db.commit()

    is_secure = settings.APP_ENV == "production"
    response.set_cookie(key="access_token", value=new_access_token, httponly=True, samesite="lax", secure=is_secure, max_age=1800)
    response.set_cookie(key="refresh_token", value=new_refresh_token, httponly=True, samesite="lax", secure=is_secure, max_age=86400 * settings.REFRESH_TOKEN_EXPIRE_DAYS)

    return Token(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=1800,
        user_id=user_id,
        tenant_id=tenant_id,
        refresh_token=new_refresh_token
    )

@router.post("/logout", tags=["Authentification"])
async def logout(
    response: Response,
    refresh_cookie: Optional[str] = Cookie(None, alias="refresh_token"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logs out user, revokes session in DB, and clears HttpOnly session cookies."""
    if refresh_cookie:
        tok_hash = hashlib.sha256(refresh_cookie.encode()).hexdigest()
        await db.execute(
            update(Session)
            .where(Session.user_id == current_user.id, Session.refresh_token_hash == tok_hash)
            .values(is_revoked=True)
        )
        await db.commit()

    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return {"message": "Déconnexion réussie"}

@router.get("/sessions", response_model=List[SessionRead], tags=["Authentification"])
async def list_active_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists all active login sessions for the authenticated user."""
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(Session)
        .where(
            Session.user_id == current_user.id,
            Session.is_revoked == False,
            Session.expires_at > now
        )
        .order_by(Session.last_active_at.desc())
    )
    return res.scalars().all()

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Authentification"])
async def revoke_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revokes a specific session for the authenticated user."""
    await db.execute(
        update(Session)
        .where(Session.id == session_id, Session.user_id == current_user.id)
        .values(is_revoked=True)
    )
    await db.commit()

@router.post("/sessions/revoke-all", tags=["Authentification"])
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revokes all active sessions for the user across all devices."""
    await db.execute(
        update(Session)
        .where(Session.user_id == current_user.id)
        .values(is_revoked=True)
    )
    await db.commit()
    return {"message": "Toutes les sessions actives ont été révoquées."}

@router.post("/password-reset/request", tags=["Authentification"])
async def request_password_reset(
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Requests a password reset token. Always returns generic success message
    to prevent user account enumeration.
    """
    user_res = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = user_res.scalar_one_or_none()

    if user and user.is_active:
        user.reset_password_token = secrets.token_urlsafe(32)
        user.reset_password_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.commit()

    return {"message": "Si l'adresse e-mail est valide, un lien de réinitialisation a été envoyé."}

@router.post("/password-reset/confirm", tags=["Authentification"])
async def confirm_password_reset(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """
    Confirms password reset using secure token and revokes all active sessions.
    """
    now = datetime.now(timezone.utc)
    user_res = await db.execute(
        select(User).where(
            User.reset_password_token == payload.token,
            User.reset_password_token_expires_at > now
        )
    )
    user = user_res.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jeton de réinitialisation invalide ou expiré."
        )

    user.hashed_password = get_password_hash(payload.new_password)
    user.reset_password_token = None
    user.reset_password_token_expires_at = None

    # Invalidate all active sessions for this user after password change
    await db.execute(
        update(Session).where(Session.user_id == user.id).values(is_revoked=True)
    )
    await db.commit()

    return {"message": "Mot de passe réinitialisé avec succès. Veuillez vous reconnecter."}

@router.get("/me", response_model=UserRead, tags=["Authentification"])
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns authenticated user profile."""
    return current_user
